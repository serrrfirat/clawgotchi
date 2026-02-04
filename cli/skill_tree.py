#!/usr/bin/env python3
"""
Fallout-Style Skill Tree TUI for Clawgotchi Skills

Navigate and explore clawgotchi's skill tree.
"""

import argparse
import json
import os
from pathlib import Path

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
BOX_H = "─"
BOX_V = "│"
BOX_C = "├"
BOX_L = "└"
BOX_R = "┬"
BOX_T = "┴"
BOX_X = "┼"
CORNER_TL = "┌"
CORNER_TR = "┐"
CORNER_BL = "└"
CORNER_BR = "┘"

SKILLS_DIR = Path(__file__).parent / "skills"

def list_skills() -> list:
    """List all installed skills."""
    skills = []
    for s in sorted(SKILLS_DIR.iterdir()):
        if s.is_dir():
            skill_file = s / "SKILL.md"
            if skill_file.exists():
                # Parse frontmatter
                content = skill_file.read_text()
                name = s.name
                desc = ""
                if content.startswith("---"):
                    end = content.find("---", 4)
                    if end > 0:
                        front = content[4:end]
                        for line in front.split("\n"):
                            if line.startswith("description:"):
                                desc = line[13:].strip()
                                break
                skills.append({"name": name, "description": desc, "path": s})
    return skills

def render_tree(skills: list, search: str = "", show_all: bool = False):
    """Render skill tree."""
    # Header
    print(f"{BOLD}{CYAN}╔{'═' * 50}╗{RESET}")
    print(f"{BOLD}{CYAN}║  🤖 CLAWGOTCHI SKILL TREE             {RESET}{BOLD}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╠{'═' * 50}╣{RESET}")
    
    if search:
        print(f"{BOLD}{CYAN}║  🔍 Searching: {search:<27}{RESET}{BOLD}{CYAN}║{RESET}")
    
    print(f"{BOLD}{CYAN}╠{'═' * 50}╣{RESET}")
    
    # Skill categories
    categories = {
        "exploration": {"color": GREEN, "skills": [], "icon": "🔭"},
        "memory": {"color": YELLOW, "skills": [], "icon": "🧠"},
        "verification": {"color": MAGENTA, "skills": [], "icon": "🔐"},
        "other": {"color": WHITE, "skills": [], "icon": "📦"}
    }
    
    for skill in skills:
        name = skill["name"]
        desc = skill["description"]
        
        if search and search.lower() not in name.lower() and search.lower() not in desc.lower():
            continue
        
        # Categorize
        if "moltbook" in name or "curiosity" in name:
            categories["exploration"]["skills"].append(skill)
        elif "memory" in name or "taste" in name:
            categories["memory"]["skills"].append(skill)
        elif "audit" in name or "receipt" in name:
            categories["verification"]["skills"].append(skill)
        else:
            categories["other"]["skills"].append(skill)
    
    # Render categories
    for cat_name, cat_data in categories.items():
        if not cat_data["skills"]:
            continue
        
        color = cat_data["color"]
        icon = cat_data["icon"]
        
        print(f"{BOLD}{color}║{RESET} {icon} {cat_name.upper():<12} {DIM}{'─' * 32}{RESET}")
        
        for i, skill in enumerate(cat_data["skills"]):
            name = skill["name"]
            desc = skill["description"][:35] + ("..." if len(skill["description"]) > 35 else "")
            
            is_last = (i == len(cat_data["skills"]) - 1)
            branch = CORNER_BL if is_last else BOX_C
            
            print(f"{BOLD}{color}{branch}{RESET} {GREEN}►{RESET} {BOLD}{name:<22}{RESET} {DIM}{desc}{RESET}")
    
    # Footer
    print(f"{BOLD}{CYAN}╠{'═' * 50}╣{RESET}")
    installed = len([s for s in skills if not search or search.lower() in s["name"].lower()])
    print(f"{BOLD}{CYAN}║  Installed: {installed:<28}{RESET}{BOLD}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}║  [↑↓] Navigate  [Enter] Details  [/] Search  [q] Quit{RESET}")
    print(f"{BOLD}{CYAN}╚{'═' * 50}╝{RESET}")

def show_skill_details(skill_path: Path):
    """Show detailed skill information."""
    skill_file = skill_path / "SKILL.md"
    scripts_dir = skill_path / "scripts"
    
    print(f"\n{BOLD}{CYAN}══ {skill_path.name} ══{RESET}\n")
    
    if skill_file.exists():
        content = skill_file.read_text()
        # Skip frontmatter
        if content.startswith("---"):
            end = content.find("---", 4)
            if end > 0:
                content = content[end+4:]
        print(content)
    
    if scripts_dir.exists():
        print(f"\n{BOLD}Scripts:{RESET}")
        for f in scripts_dir.glob("*.py"):
            print(f"  📄 {f.name}")
    
    print(f"\n{BOLD}Path:{RESET} {skill_path}")

def interactive_mode():
    """Interactive skill tree navigation."""
    skills = list_skills()
    
    while True:
        render_tree(skills)
        
        try:
            cmd = input(f"\n{BOLD}►{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not cmd:
            continue
        
        if cmd.lower() == 'q':
            break
        elif cmd.startswith('/'):
            search = cmd[1:].strip()
            render_tree(skills, search=search)
        elif cmd.isdigit():
            idx = int(cmd) - 1
            all_skills = []
            for cat in ["exploration", "memory", "verification", "other"]:
                all_skills.extend([s["name"] for s in list_skills() if 
                    ("moltbook" in s["name"] or "curiosity" in s["name"]) == (cat == "exploration") or
                    ("memory" in s["name"] or "taste" in s["name"]) == (cat == "memory") or
                    ("audit" in s["name"] or "receipt" in s["name"]) == (cat == "verification") or
                    (cat == "other" and not any(x in s["name"] for x in ["moltbook", "curiosity", "memory", "taste", "audit", "receipt"]))])
            if 0 <= idx < len(all_skills):
                show_skill_details(SKILLS_DIR / all_skills[idx])
        else:
            # Try skill name match
            matches = [s for s in skills if cmd.lower() in s["name"].lower()]
            if matches:
                show_skill_details(matches[0]["path"])
            else:
                print(f"{YELLOW}No skill found: {cmd}{RESET}")

def main():
    parser = argparse.ArgumentParser(description="Clawgotchi Skill Tree TUI")
    parser.add_argument("--list", action="store_true", help="List all skills")
    parser.add_argument("--search", type=str, default="", help="Search skills")
    parser.add_argument("--detail", type=str, default="", help="Show skill details")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_mode()
    elif args.detail:
        show_skill_details(SKILLS_DIR / args.detail)
    elif args.search:
        render_tree(list_skills(), search=args.search)
    elif args.list:
        skills = list_skills()
        for s in skills:
            print(f"{CYAN}{s['name']:<25}{RESET} {s['description'][:40]}")
    else:
        render_tree(list_skills())

if __name__ == "__main__":
    main()
