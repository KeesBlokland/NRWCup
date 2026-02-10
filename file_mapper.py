import os
import re
import sys
import ast
from collections import defaultdict

class FlaskDependencyMapper:
    def __init__(self, app_root):
        self.app_root = app_root
        self.blueprint_routes = {}  # Blueprint name -> route definitions
        self.route_templates = {}   # Route -> templates
        self.route_services = {}    # Route -> services used
        self.template_dependencies = {}  # Template -> included templates
        
    def analyze(self):
        """Analyze the entire application"""
        self.find_blueprints()
        self.find_templates()
        self.map_routes_to_templates()
        
    def find_blueprints(self):
        """Find all blueprint files and their routes"""
        for root, _, files in os.walk(self.app_root):
            for file in files:
                if file.startswith('bp_') and file.endswith('.py'):
                    self.analyze_blueprint_file(os.path.join(root, file))
    
    def analyze_blueprint_file(self, filepath):
        """Extract route definitions from a blueprint file"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract blueprint name
        bp_match = re.search(r'(\w+)_bp\s*=\s*Blueprint', content)
        if not bp_match:
            return
            
        blueprint_name = bp_match.group(1)
        self.blueprint_routes[blueprint_name] = []
        
        # Find route definitions
        route_patterns = [
            r'@{}_bp\.route\([\'"]([^\'"]+)[\'"]'.format(blueprint_name),
            r'@{}_bp\.route\([\'"]([^\'"]+)[\'"]'.format(blueprint_name.replace('_', '\.'))
        ]
        
        for pattern in route_patterns:
            for match in re.finditer(pattern, content):
                route = match.group(1)
                
                # Find the function name that follows this route
                func_match = re.search(r'def\s+(\w+)\(', content[match.end():match.end()+200])
                if func_match:
                    function_name = func_match.group(1)
                    self.blueprint_routes[blueprint_name].append({
                        'route': route,
                        'function': function_name,
                        'file': filepath
                    })
                    
                    # Look for template rendering in this function
                    func_content = self.extract_function(content, function_name)
                    if func_content:
                        self.find_templates_in_function(func_content, blueprint_name, route)
                        self.find_service_calls(func_content, blueprint_name, route)
    
    def extract_function(self, content, function_name):
        """Extract a function's content from file content"""
        pattern = r'def\s+{}[^:]*:(.+?)(?=\n\S+|\Z)'.format(function_name)
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
        return None
    
    def find_templates_in_function(self, func_content, blueprint, route):
        """Find template rendering in a function"""
        template_pattern = r'render_template\([\'"]([^\'"]+)[\'"]'
        for match in re.finditer(template_pattern, func_content):
            template = match.group(1)
            key = f"{blueprint}.{route}"
            if key not in self.route_templates:
                self.route_templates[key] = []
            self.route_templates[key].append(template)
    
    def find_service_calls(self, func_content, blueprint, route):
        """Find service calls in a function"""
        # This is simplified - would need more complex parsing for real usage
        service_pattern = r'(\w+)_service\.(\w+)'
        for match in re.finditer(service_pattern, func_content):
            service = match.group(1)
            method = match.group(2)
            key = f"{blueprint}.{route}"
            if key not in self.route_services:
                self.route_services[key] = []
            self.route_services[key].append(f"{service}_service.{method}")
    
    def find_templates(self):
        """Find all templates and their dependencies"""
        templates_dir = os.path.join(self.app_root, 'templates')
        if not os.path.exists(templates_dir):
            return
            
        for root, _, files in os.walk(templates_dir):
            for file in files:
                if file.endswith('.html'):
                    template_path = os.path.relpath(os.path.join(root, file), templates_dir)
                    self.analyze_template(os.path.join(root, file), template_path)
    
    def analyze_template(self, filepath, template_path):
        """Find dependencies in a template"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find extends and includes
        extends_pattern = r'{%\s*extends\s+[\'"]([^\'"]+)[\'"]'
        include_pattern = r'{%\s*include\s+[\'"]([^\'"]+)[\'"]'
        
        self.template_dependencies[template_path] = []
        
        for pattern in [extends_pattern, include_pattern]:
            for match in re.finditer(pattern, content):
                dependency = match.group(1)
                self.template_dependencies[template_path].append(dependency)
    
    def map_routes_to_templates(self):
        """Create a complete map of routes to all related files"""
        self.route_file_map = {}
        
        for blueprint, routes in self.blueprint_routes.items():
            for route_info in routes:
                route = route_info['route']
                key = f"{blueprint}.{route}"
                
                if key not in self.route_file_map:
                    self.route_file_map[key] = {
                        'blueprint_file': route_info['file'],
                        'templates': [],
                        'services': [],
                        'models': []  # Would need additional analysis
                    }
                
                # Add templates
                if key in self.route_templates:
                    for template in self.route_templates[key]:
                        if template not in self.route_file_map[key]['templates']:
                            self.route_file_map[key]['templates'].append(template)
                            
                            # Add template dependencies
                            self._add_template_dependencies(template, self.route_file_map[key]['templates'])
                
                # Add services
                if key in self.route_services:
                    for service in self.route_services[key]:
                        service_name = service.split('.')[0]
                        if service_name not in self.route_file_map[key]['services']:
                            self.route_file_map[key]['services'].append(service_name)
    
    def _add_template_dependencies(self, template, template_list):
        """Recursively add template dependencies"""
        if template in self.template_dependencies:
            for dependency in self.template_dependencies[template]:
                if dependency not in template_list:
                    template_list.append(dependency)
                    self._add_template_dependencies(dependency, template_list)
    
    def get_files_for_route(self, blueprint_name, route):
        """Get all files related to a specific route"""
        key = f"{blueprint_name}.{route}"
        if key in self.route_file_map:
            return self.route_file_map[key]
        return None
    
    def get_files_for_url(self, url):
        """Get all files related to a specific URL"""
        # This would require more complex matching
        # For now, we'll do a simple substring match
        for key, files in self.route_file_map.items():
            blueprint, route = key.split('.')
            if route in url or url in route:
                return {
                    'key': key,
                    'files': files
                }
        return None
    
    def generate_report(self):
        """Generate a report of all routes and their related files"""
        report = []
        for key, files in self.route_file_map.items():
            blueprint, route = key.split('.')
            report.append({
                'blueprint': blueprint,
                'route': route,
                'files': files
            })
        return report

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python file_mapper.py [app_directory] <url>")
        sys.exit(1)
        
    app_dir = sys.argv[1]
    
    mapper = FlaskDependencyMapper(app_dir)
    mapper.analyze()
    
    if len(sys.argv) >= 3:
        # Find files for a specific URL
        url = sys.argv[2]
        result = mapper.get_files_for_url(url)
        if result:
            print(f"Files related to {url}:")
            print(f"Blueprint file: {result['files']['blueprint_file']}")
            print("Templates:")
            for template in result['files']['templates']:
                print(f"  - templates/{template}")
            print("Services:")
            for service in result['files']['services']:
                print(f"  - services/{service}_service.py")
        else:
            print(f"No files found for URL {url}")
    else:
        # Print all routes
        report = mapper.generate_report()
        for item in report:
            print(f"{item['blueprint']}: {item['route']}")
            print(f"  Blueprint file: {item['files']['blueprint_file']}")
            print("  Templates:")
            for template in item['files']['templates']:
                print(f"    - templates/{template}")
            if item['files']['services']:
                print("  Services:")
                for service in item['files']['services']:
                    print(f"    - services/{service}_service.py")
            print()