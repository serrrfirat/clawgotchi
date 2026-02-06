"""
Skill Dependency Analyzer
Parses skill.md files and reports missing referenced skills.
"""
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


def extract_skill_name(skill_md: str) -> str:
    """Extract skill name from YAML frontmatter."""
    name_match = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?\s*$', skill_md, re.MULTILINE)
    return name_match.group(1).strip() if name_match else ""


def extract_referenced_skills(skill_md: str) -> List[str]:
    """Extract skill names referenced in the skill description."""
    # Remove code blocks (```...```)
    content = re.sub(r'```[\s\S]*?```', '', skill_md)
    # Remove inline code (`...`)
    content = re.sub(r'`[^`]+`', '', content)
    
    refs = []
    
    # Find quoted skill references: "skill-name" or 'skill-name'
    quoted_matches = re.findall(r'["\']([a-z0-9\-]+)["\']', content, re.IGNORECASE)
    refs.extend([m.lower() for m in quoted_matches])
    
    # Filter out common words that aren't skill names
    # Skills typically have hyphens (e.g., "memory-query", "decision-logger")
    skill_pattern = re.compile(r'^[a-z]+-[a-z0-9]+$')
    refs = [r for r in refs if skill_pattern.match(r)]
    
    return list(set(refs))


def get_all_skills(skills_dir: str) -> Dict[str, str]:
    """Get all installed skill names and their file paths."""
    skills = {}
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return skills
    
    for skill_file in skills_path.glob("*/SKILL.md"):
        content = skill_file.read_text()
        name = extract_skill_name(content)
        if name:
            skills[name.lower()] = str(skill_file)
    return skills


def analyze_skill_dependencies(skills_dir: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Analyze all skills for dependencies.
    Returns (missing_deps, installed_deps) dicts keyed by skill name.
    """
    installed = get_all_skills(skills_dir)
    missing = {}
    installed_refs = {}
    
    for skill_name, skill_path in installed.items():
        content = Path(skill_path).read_text()
        refs = extract_referenced_skills(content)
        
        # Filter out self-references
        refs = [r for r in refs if r != skill_name]
        
        installed_refs[skill_name] = [r for r in refs if r in installed]
        missing[skill_name] = [r for r in refs if r not in installed]
    
    return missing, installed_refs


def report_missing_dependencies(skills_dir: str) -> str:
    """Generate a report of missing skill dependencies."""
    missing, installed = analyze_skill_dependencies(skills_dir)
    
    lines = ["# Skill Dependency Report", ""]
    
    # Missing dependencies (actionable)
    has_missing = False
    for skill, deps in sorted(missing.items()):
        if deps:
            if not has_missing:
                lines.append("## Missing Dependencies (需要安装)")
                lines.append("")
                has_missing = True
            lines.append(f"- **{skill}** requires: {', '.join(deps)}")
    
    if not has_missing:
        lines.append("## Missing Dependencies (需要安装)")
        lines.append("- No missing dependencies found ✓")
    
    lines.append("")
    lines.append("## Installed Dependencies")
    lines.append("")
    
    has_installed = False
    for skill, deps in sorted(installed.items()):
        if deps:
            has_installed = True
            lines.append(f"- **{skill}** → {', '.join(deps)}")
    
    if not has_installed:
        lines.append("- No inter-skill dependencies found")
    
    return "\n".join(lines)
