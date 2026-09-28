"""Build the public site page (docs/index.html) from the page template and derived data.

Run from the repository root after analysis/marfa_occlusion.py:
    python analysis/build_site.py
"""
template = open("analysis/occlusion_template.html", encoding="utf-8").read()
data = open("data/derived/occlusion_page.json", encoding="utf-8").read()
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n')
# the template starts with <title>, <link> and <style>; everything up to </style> belongs in <head>
split = template.index("</style>") + len("</style>")
page = head + template[:split] + "\n</head>\n<body>\n" + template[split:].replace("__DATA__", data) + "\n</body>\n</html>\n"
open("docs/index.html", "w", encoding="utf-8").write(page)
print(f"docs/index.html written ({len(page)/1024:.0f} KB)")
