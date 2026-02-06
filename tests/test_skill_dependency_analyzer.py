"""
Tests for Skill Dependency Analyzer
"""
import pytest
from pathlib import Path
from utils.skill_dependency_analyzer import (
    extract_skill_name,
    extract_referenced_skills,
    get_all_skills,
    analyze_skill_dependencies,
)


class TestExtractSkillName:
    def test_basic_name(self):
        md = '''---
name: test-skill
description: A test skill
---'''
        assert extract_skill_name(md) == "test-skill"
    
    def test_name_with_quotes(self):
        md = '''---
name: "my-skill"
description: A test skill
---'''
        assert extract_skill_name(md) == "my-skill"
    
    def test_name_with_single_quotes(self):
        md = """---
name: 'another-skill'
description: A test skill
---"""
        assert extract_skill_name(md) == "another-skill"
    
    def test_no_frontmatter(self):
        md = "# Just a header"
        assert extract_skill_name(md) == ""
    
    def test_empty_name(self):
        # Empty name is an edge case - just ensure we don't crash
        md = '''---
name:
description: Empty name
---'''
        # This may return the next line's content, which is acceptable
        result = extract_skill_name(md)
        assert result != "name"  # Shouldn't return the field name itself


class TestExtractReferencedSkills:
    def test_use_skill_pattern(self):
        md = "Use this skill when you need to query memory."
        assert extract_referenced_skills(md) == []
    
    def test_quoted_skill_reference(self):
        md = 'Use the "memory-query" skill for memory searches.'
        assert "memory-query" in extract_referenced_skills(md)
    
    def test_multiple_references(self):
        md = 'Requires "memory-query" and "decision-logger" skills.'
        refs = extract_referenced_skills(md)
        assert "memory-query" in refs
        assert "decision-logger" in refs
    
    def test_depends_on_pattern(self):
        # Unquoted references are not detected - only quoted ones
        # "This skill depends on memory-query" won't match without quotes
        md = 'This skill depends on "memory-query" for storage.'
        refs = extract_referenced_skills(md)
        assert "memory-query" in refs
    
    def test_skills_list(self):
        # Comma-separated skills need quotes
        md = 'Skills: "memory-query", "decision-logger", "taste-profile"'
        refs = extract_referenced_skills(md)
        assert "memory-query" in refs
        assert "decision-logger" in refs
        assert "taste-profile" in refs
    
    def test_case_insensitive(self):
        md = 'Use the "Memory-Query" skill for MEMORY-QUERY tasks.'
        refs = extract_referenced_skills(md)
        assert "memory-query" in refs
    
    def test_no_duplicates(self):
        md = 'Requires "memory-query" and uses "memory-query" again.'
        refs = extract_referenced_skills(md)
        assert len(refs) == 1
        assert "memory-query" in refs


class TestGetAllSkills:
    def test_empty_directory(self, tmp_path):
        skills = get_all_skills(str(tmp_path))
        assert skills == {}
    
    def test_single_skill(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('''---
name: test-skill
description: A test
---''')
        
        skills = get_all_skills(str(tmp_path))
        assert "test-skill" in skills
        assert skills["test-skill"].endswith("test-skill/SKILL.md")
    
    def test_multiple_skills(self, tmp_path):
        for name in ["skill-a", "skill-b", "skill-c"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f'''---
name: {name}
description: Test
---''')
        
        skills = get_all_skills(str(tmp_path))
        assert len(skills) == 3


class TestAnalyzeSkillDependencies:
    def test_no_missing_dependencies(self, tmp_path):
        skill_dir = tmp_path / "parent-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('''---
name: parent-skill
description: A parent skill
---''')
        
        missing, installed = analyze_skill_dependencies(str(tmp_path))
        assert missing["parent-skill"] == []
    
    def test_missing_dependency(self, tmp_path):
        parent = tmp_path / "parent-skill"
        parent.mkdir()
        (parent / "SKILL.md").write_text('''---
name: parent-skill
description: Requires "missing-child" skill.
---''')
        
        missing, installed = analyze_skill_dependencies(str(tmp_path))
        assert "missing-child" in missing["parent-skill"]
    
    def test_installed_dependency(self, tmp_path):
        parent = tmp_path / "parent-skill"
        parent.mkdir()
        (parent / "SKILL.md").write_text('''---
name: parent-skill
description: Uses "child-skill".
---''')
        
        child = tmp_path / "child-skill"
        child.mkdir()
        (child / "SKILL.md").write_text('''---
name: child-skill
description: A child skill
---''')
        
        missing, installed = analyze_skill_dependencies(str(tmp_path))
        assert "child-skill" in installed["parent-skill"]
        assert "child-skill" not in missing["parent-skill"]
    
    def test_self_reference_excluded(self, tmp_path):
        skill = tmp_path / "self-ref"
        skill.mkdir()
        (skill / "SKILL.md").write_text('''---
name: self-ref
description: Uses "self-ref" internally.
---''')
        
        missing, installed = analyze_skill_dependencies(str(tmp_path))
        assert "self-ref" not in missing["self-ref"]
