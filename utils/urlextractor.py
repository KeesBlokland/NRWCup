import re
import os

def extract_urls_from_file(file_path):
    """Extract all url_for() calls from a file"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to match Flask url_for() calls
    pattern = r"url_for\('([^']+)'[^)]*\)"
    matches = re.finditer(pattern, content)
    
    urls = {}
    for match in matches:
        url = match.group(1)
        line_num = content[:match.start()].count('\n') + 1
        if url not in urls:
            urls[url] = []
        urls[url].append(line_num)
        
    return urls

def process_documents(input_file):
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Extract document sections
    doc_pattern = r'<document_content>(.*?)</document_content>'
    documents = re.findall(doc_pattern, content, re.DOTALL)
    
    all_urls = {}
    
    for doc in documents:
        # Look for Flask url_for patterns
        pattern = r"url_for\('([^']+)'[^)]*\)"
        matches = re.finditer(pattern, doc)
        
        for match in matches:
            url = match.group(1)
            if url not in all_urls:
                all_urls[url] = 0
            all_urls[url] += 1

    # Sort by frequency
    sorted_urls = dict(sorted(all_urls.items(), key=lambda x: x[1], reverse=True))
    
    return sorted_urls

def write_report(urls, output_file="url_analysis.txt"):
    with open(output_file, 'w') as f:
        f.write("URL Route Analysis Report\n")
        f.write("=" * 50 + "\n\n")
        
        for url, count in urls.items():
            f.write(f"Route: {url}\n")
            f.write(f"Referenced {count} times\n")
            f.write("-" * 30 + "\n")

if __name__ == "__main__":
    input_file = "claude_documents_latest.txt"  # Your input file
    
    if not os.path.exists(input_file):
        print(f"Error: Cannot find {input_file}")
        exit(1)
        
    urls = process_documents(input_file)
    write_report(urls)
    
    print(f"\nAnalysis complete! Check url_analysis.txt for results.")
