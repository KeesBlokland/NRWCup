"""
File: route_analyzer.py
Rev: 1.0.0
Created: 2024-12-01
Last Modified: 2024-12-01
Author: Claude

Description: 
Analyzes Flask application route definitions and usages across Python and template files.
The script identifies:
- All defined routes and their locations
- Routes used in templates but not defined in Python files
- Routes defined but never used in templates
Input: Expects a claude_documents_latest.txt file in the same directory
Output: Generates route_analysis.txt with detailed route analysis
"""

import re
from collections import defaultdict

def extract_route_definitions(content, filename):
    """Extract routes defined in Python files"""
    defined_routes = {}
    
    # Pattern to match route decorators
    route_pattern = r"@\w+_routes\.route\(['\"]([^'\"]+)['\"]"
    # Pattern to match blueprint definitions
    blueprint_pattern = r"(\w+)_routes\s*=\s*Blueprint\(['\"](\w+)['\"]"
    
    # Find all blueprint definitions
    blueprints = {}
    for match in re.finditer(blueprint_pattern, content):
        var_name, blueprint_name = match.groups()
        blueprints[var_name] = blueprint_name
    
    # Find all routes
    for match in re.finditer(route_pattern, content):
        route = match.group(1)
        line_number = content[:match.start()].count('\n') + 1
        # Look backwards for the associated function name
        func_pattern = r"def\s+(\w+)\s*\("
        func_match = re.search(func_pattern, content[match.end():match.end()+200])
        if func_match:
            func_name = func_match.group(1)
            # Find which blueprint this belongs to
            bp_content = content[:match.start()].split('\n')[-5:]  # Look at last 5 lines before route
            for bp_var, bp_name in blueprints.items():
                if any(bp_var in line for line in bp_content):
                    route_name = f"{bp_name}.{func_name}"
                    defined_routes[route_name] = {
                        'path': route,
                        'file': filename,
                        'line': line_number
                    }
                    break
    
    return defined_routes

def extract_template_urls(content, filename):
    """Extract url_for calls from templates"""
    used_routes = {}
    url_pattern = r"url_for\(['\"]([^'\"]+)['\"]"
    
    for match in re.finditer(url_pattern, content):
        route = match.group(1)
        line_number = content[:match.start()].count('\n') + 1
        if route not in used_routes:
            used_routes[route] = []
        used_routes[route].append({
            'file': filename,
            'line': line_number
        })
    
    return used_routes

def analyze_routes(input_file):
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Extract individual documents
    doc_pattern = r'<source>(.+?)</source>\s*<document_content>(.*?)</document_content>'
    documents = re.finditer(doc_pattern, content, re.DOTALL)
    
    all_defined_routes = {}
    all_used_routes = defaultdict(list)
    
    for doc in documents:
        filename = doc.group(1)
        content = doc.group(2)
        
        if filename.endswith('.py'):
            routes = extract_route_definitions(content, filename)
            all_defined_routes.update(routes)
        elif filename.endswith('.html'):
            routes = extract_template_urls(content, filename)
            for route, locations in routes.items():
                all_used_routes[route].extend(locations)
    
    # Find mismatches
    undefined_routes = {route: locations for route, locations in all_used_routes.items() 
                       if route not in all_defined_routes}
    unused_routes = {route: info for route, info in all_defined_routes.items() 
                    if route not in all_used_routes}
    
    # Generate report
    with open('route_analysis.txt', 'w') as f:
        f.write("Route Analysis Report\n")
        f.write("=" * 50 + "\n\n")
        
        f.write("Defined Routes:\n")
        f.write("-" * 50 + "\n")
        for route_name, info in sorted(all_defined_routes.items()):
            f.write(f"Route: {route_name}\n")
            f.write(f"  Path: {info['path']}\n")
            f.write(f"  Defined in: {info['file']} (line {info['line']})\n")
            f.write("\n")
        
        f.write("\nUndefined Routes (used in templates but not found in Python files):\n")
        f.write("-" * 50 + "\n")
        for route, locations in sorted(undefined_routes.items()):
            f.write(f"Route: {route}\n")
            f.write("  Used in:\n")
            for loc in locations:
                f.write(f"    - {loc['file']} (line {loc['line']})\n")
            f.write("\n")
        
        f.write("\nUnused Routes (defined but not referenced in templates):\n")
        f.write("-" * 50 + "\n")
        for route, info in sorted(unused_routes.items()):
            f.write(f"Route: {route}\n")
            f.write(f"  Path: {info['path']}\n")
            f.write(f"  Defined in: {info['file']} (line {info['line']})\n")
            f.write("\n")

if __name__ == "__main__":
    analyze_routes("claude_documents_latest.txt")
    print("Analysis complete! Check route_analysis.txt for results.")