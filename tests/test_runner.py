"""Test runner script for running tests with different configurations."""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("✅ SUCCESS")
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ FAILED")
        print("STDERR:")
        print(e.stderr)
        if e.stdout:
            print("STDOUT:")
            print(e.stdout)
        return False


def main():
    """Main test runner function."""
    # Change to the project root directory
    project_root = Path(__file__).parent.parent
    print(f"Running tests from: {project_root}")
    
    test_commands = [
        {
            "cmd": "python -m pytest tests/unit/ -m unit -v",
            "description": "Unit Tests"
        },
        {
            "cmd": "python -m pytest tests/integration/ -m integration -v",
            "description": "Integration Tests"
        },
        {
            "cmd": "python -m pytest tests/ -v --cov=main --cov=src --cov-report=term-missing",
            "description": "All Tests with Coverage"
        },
        {
            "cmd": "python -m pytest tests/ --tb=short",
            "description": "Quick Test Run"
        }
    ]
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "unit":
            commands_to_run = [test_commands[0]]
        elif test_type == "integration":
            commands_to_run = [test_commands[1]]
        elif test_type == "coverage":
            commands_to_run = [test_commands[2]]
        elif test_type == "quick":
            commands_to_run = [test_commands[3]]
        else:
            print(f"Unknown test type: {test_type}")
            print("Available options: unit, integration, coverage, quick")
            return 1
    else:
        # Run all tests by default
        commands_to_run = test_commands
    
    # Change to project directory
    original_dir = Path.cwd()
    try:
        import os
        os.chdir(project_root)
        
        success_count = 0
        total_count = len(commands_to_run)
        
        for test_cmd in commands_to_run:
            if run_command(test_cmd["cmd"], test_cmd["description"]):
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Passed: {success_count}/{total_count}")
        print(f"Failed: {total_count - success_count}/{total_count}")
        
        if success_count == total_count:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("💥 SOME TESTS FAILED!")
            return 1
            
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    exit(main())