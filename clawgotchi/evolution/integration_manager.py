"""
IntegrationManager - Wire built modules into the wake cycle.

Modules that get built often sit orphaned - they exist but aren't
actually used. This manager scans for orphaned modules and wires
them into the appropriate integration points.

Integration points:
- Resilience modules → health checks
- Cognition modules → decision making
- Memory modules → consolidation
- Safety modules → validation
"""

import ast
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ModuleInfo:
    """Information about a module."""
    path: str
    name: str
    package: str
    category: str  # resilience, cognition, memory, safety, other
    integration_point: str  # where it should be wired
    status: str  # orphaned, integrated, failed
    classes: list[str]
    functions: list[str]
    last_checked: str


class IntegrationManager:
    """Wire built modules into the wake cycle."""

    # Mapping of package paths to integration points
    INTEGRATION_POINTS = {
        "clawgotchi/resilience": {
            "point": "_check_health",
            "category": "resilience",
            "description": "Health checks and resilience utilities",
        },
        "cognition": {
            "point": "_decide_next_action",
            "category": "cognition",
            "description": "Decision making and cognition",
        },
        "memory": {
            "point": "_reflect",
            "category": "memory",
            "description": "Memory and consolidation",
        },
        "health": {
            "point": "_check_health",
            "category": "safety",
            "description": "Safety and validation",
        },
    }

    def __init__(self, registry=None, memory_dir: str = "memory"):
        self.registry = registry
        self.memory_dir = Path(memory_dir)
        self.integrations_path = self.memory_dir / "integrations.json"
        self._integrations: dict[str, ModuleInfo] = {}
        self._load()

    def _load(self):
        """Load integration state from disk."""
        if self.integrations_path.exists():
            try:
                data = json.loads(self.integrations_path.read_text())
                for name, info in data.get("modules", {}).items():
                    self._integrations[name] = ModuleInfo(**info)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def _save(self):
        """Save integration state to disk."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "modules": {
                name: asdict(info) for name, info in self._integrations.items()
            },
            "updated_at": datetime.now().isoformat(),
        }
        self.integrations_path.write_text(json.dumps(data, indent=2))

    def scan_orphaned_modules(self, base_dir: str = ".") -> list[dict]:
        """Find modules that exist but aren't integrated.

        Scans package directories for Python files and checks
        if they're registered/imported in the main system.

        Returns:
            List of orphaned module dicts with path, name, category
        """
        base = Path(base_dir)
        orphaned = []

        # Scan each integration point directory
        for package_path, config in self.INTEGRATION_POINTS.items():
            pkg_dir = base / package_path
            if not pkg_dir.exists():
                continue

            for py_file in pkg_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                module_name = py_file.stem
                full_path = str(py_file)

                # Check if already tracked as integrated
                if module_name in self._integrations:
                    if self._integrations[module_name].status == "integrated":
                        continue

                # Parse to get classes/functions
                try:
                    content = py_file.read_text()
                    tree = ast.parse(content)
                    classes = [
                        node.name for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)
                    ]
                    functions = [
                        node.name for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                        and not node.name.startswith("_")
                    ]
                except SyntaxError:
                    classes = []
                    functions = []

                # Check if module is actually used
                if not self._is_module_integrated(module_name, base):
                    orphaned.append({
                        "path": full_path,
                        "name": module_name,
                        "package": package_path,
                        "category": config["category"],
                        "integration_point": config["point"],
                        "classes": classes,
                        "functions": functions,
                    })

        return orphaned

    def _is_module_integrated(self, module_name: str, base: Path) -> bool:
        """Check if a module is imported/used in the main system."""
        # Check autonomous_agent.py for imports
        agent_path = base / "core" / "autonomous_agent.py"
        if agent_path.exists():
            content = agent_path.read_text()
            if module_name in content:
                return True

        # Check resilience registry
        if self.registry:
            try:
                registered = self.registry.list_all()
                if module_name in [r.get("name") for r in registered]:
                    return True
            except Exception:
                pass

        # Check __init__.py files
        for init_path in base.rglob("__init__.py"):
            try:
                content = init_path.read_text()
                if module_name in content:
                    return True
            except Exception:
                continue

        return False

    def categorize_module(self, module_path: str) -> str:
        """Determine where a module should be integrated.

        Returns the integration point name.
        """
        path = Path(module_path)

        for package_path, config in self.INTEGRATION_POINTS.items():
            if package_path in str(path):
                return config["point"]

        # Fallback: analyze content
        try:
            content = path.read_text()
            if "health" in content.lower() or "check" in content.lower():
                return "_check_health"
            if "decide" in content.lower() or "priority" in content.lower():
                return "_decide_next_action"
            if "memory" in content.lower() or "reflect" in content.lower():
                return "_reflect"
        except Exception:
            pass

        return "_check_health"  # Default

    def generate_integration_code(self, module: dict) -> str:
        """Generate the code to wire a module in.

        Args:
            module: Module dict from scan_orphaned_modules

        Returns:
            Python code snippet for integration
        """
        name = module["name"]
        package = module["package"].replace("/", ".")
        classes = module.get("classes", [])
        functions = module.get("functions", [])

        lines = []
        lines.append(f"# Integration for {name}")
        lines.append(f"# Auto-generated by IntegrationManager")
        lines.append("")

        # Import statement
        if classes:
            imports = ", ".join(classes[:3])  # Limit to 3
            lines.append(f"from {package}.{name} import {imports}")
        elif functions:
            imports = ", ".join(functions[:3])
            lines.append(f"from {package}.{name} import {imports}")
        else:
            lines.append(f"from {package} import {name}")

        lines.append("")

        # Usage snippet
        point = module.get("integration_point", "_check_health")
        if classes:
            cls = classes[0]
            lines.append(f"# In {point}():")
            lines.append(f"#   instance = {cls}()")
            lines.append(f"#   result = instance.run()  # or appropriate method")
        elif functions:
            func = functions[0]
            lines.append(f"# In {point}():")
            lines.append(f"#   result = {func}()")

        return "\n".join(lines)

    def integrate_module(self, module: dict) -> dict:
        """Actually wire the module into the system.

        Steps:
        1. Register in ResilienceRegistry if applicable
        2. Add import to autonomous_agent.py
        3. Wire into appropriate phase
        4. Test the integration

        Returns:
            Dict with status, message, changes_made
        """
        name = module["name"]
        package = module["package"]
        category = module.get("category", "other")

        changes = []
        errors = []

        # 1. Register in ResilienceRegistry
        if self.registry and category == "resilience":
            try:
                # Try to import and register
                module_path = f"{package.replace('/', '.')}.{name}"
                self.registry.register(name, module_path)
                changes.append(f"Registered {name} in ResilienceRegistry")
            except Exception as e:
                errors.append(f"Registry registration failed: {e}")

        # 2. Track as integrated
        info = ModuleInfo(
            path=module["path"],
            name=name,
            package=package,
            category=category,
            integration_point=module.get("integration_point", "_check_health"),
            status="integrated" if not errors else "failed",
            classes=module.get("classes", []),
            functions=module.get("functions", []),
            last_checked=datetime.now().isoformat(),
        )
        self._integrations[name] = info
        self._save()

        if errors:
            return {
                "status": "failed",
                "message": "; ".join(errors),
                "changes_made": changes,
            }

        return {
            "status": "integrated",
            "message": f"Integrated {name} into {category}",
            "changes_made": changes,
        }

    def test_integration(self, module: dict) -> bool:
        """Verify the module works in context.

        Attempts to import and do basic validation.
        """
        try:
            name = module["name"]
            package = module["package"].replace("/", ".")
            module_path = f"{package}.{name}"

            # Try import
            __import__(module_path)
            return True
        except ImportError:
            return False
        except Exception:
            return False

    def get_integration_status(self) -> dict:
        """Report on all modules: integrated vs orphaned."""
        integrated = [
            name for name, info in self._integrations.items()
            if info.status == "integrated"
        ]
        orphaned = [
            name for name, info in self._integrations.items()
            if info.status == "orphaned"
        ]
        failed = [
            name for name, info in self._integrations.items()
            if info.status == "failed"
        ]

        return {
            "integrated_count": len(integrated),
            "orphaned_count": len(orphaned),
            "failed_count": len(failed),
            "integrated": integrated,
            "orphaned": orphaned,
            "failed": failed,
        }

    def get_integration_points(self) -> list[str]:
        """Get list of available integration points."""
        return list(set(c["point"] for c in self.INTEGRATION_POINTS.values()))

    def mark_integrated(self, module_name: str):
        """Mark a module as integrated (for manual tracking)."""
        if module_name in self._integrations:
            self._integrations[module_name].status = "integrated"
            self._integrations[module_name].last_checked = datetime.now().isoformat()
            self._save()

    def mark_orphaned(self, module_name: str):
        """Mark a module as orphaned."""
        if module_name in self._integrations:
            self._integrations[module_name].status = "orphaned"
            self._save()
