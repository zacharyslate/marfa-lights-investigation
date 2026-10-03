"""Build the sight-line report page (docs/sightlines.html) from the page template and derived data.

Run from the repository root after analysis/marfa_occlusion.py:
    python analysis/build_site.py
"""
template = open("analysis/occlusion_template.html", encoding="utf-8").read()
data = open("data/derived/occlusion_page.json", encoding="utf-8").read()
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700'
        '&family=JetBrains+Mono:wght@400;600&family=Source+Sans+3:wght@400;600&display=swap">\n'
        '<link rel="stylesheet" href="assets/site.css?v=14">\n'
        '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n')
# the shared site header and footer keep their own fonts and layout; the report's page-wide rules must not reach them
shell = ('<style>body{padding:0}.wrap{padding:28px 20px 56px}th{text-transform:none;letter-spacing:0}'
         '#bar,#foot{--f-disp:"Barlow Condensed","Arial Narrow",system-ui,sans-serif;--f-body:"Source Sans 3",system-ui,sans-serif;'
         '--f-mono:"JetBrains Mono",ui-monospace,monospace;font-family:var(--f-body)}'
         'header#bar{display:block}#bar svg,#foot svg{display:inline-block;width:auto}#bar p,#foot p{max-width:none}'
         '#foot{font-size:14px}</style>\n')
# the template starts with <title>, <link> and <style>; everything up to </style> belongs in <head>
split = template.index("</style>") + len("</style>")
page = (head + template[:split] + "\n" + shell + "</head>\n<body>\n<header id=\"bar\"></header>\n"
        + template[split:].replace("__DATA__", data)
        + '\n<footer id="foot"></footer>\n<script src="assets/site.js?v=14"></script>\n</body>\n</html>\n')
open("docs/sightlines.html", "w", encoding="utf-8").write(page)
print(f"docs/sightlines.html written ({len(page)/1024:.0f} KB)")
