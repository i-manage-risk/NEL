"""A consistent navigation and progressive detail shell, applied by all generators."""
import re

def apply_chrome(html, page):
    if 'assets/detail-shell.js' in html:
        return html
    html = re.sub(r'<nav class="site-nav"[^>]*>.*?</nav>', '', html, count=1, flags=re.S)
    html = html.replace('</head>', '<link rel="stylesheet" href="assets/workspace.css"><link rel="stylesheet" href="assets/detail-shell.css"></head>')
    html = html.replace('</body>', '<script src="assets/detail-shell.js" data-page="'+page+'"></script></body>')
    return '\n'.join(line.rstrip() for line in html.split('\n'))
