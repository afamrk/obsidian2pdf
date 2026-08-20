# obsidian2pdf

Export an Obsidian note or folder to a single PDF — including a page preset
matching the Kobo Libra Colour screen so notes read comfortably on the device.

## Install

    python3 -m venv .venv
    .venv/bin/pip install -e .

WeasyPrint needs Pango; on Debian/Ubuntu:
`sudo apt install libpango-1.0-0 libpangoft2-1.0-0`.

## Usage

    obsidian2pdf <note.md | folder> [options]

    -o, --output PATH     output PDF (default: <input name>.pdf next to input)
    -s, --size SIZE       a4 (default), a5, kobo-libra-colour, kobo-clara,
                          custom "1264x1680@300" (px@dpi) or "91x120mm";
                          ignored when --format is epub (reflowable, no
                          fixed page)
    --format NAME         pdf (default) | epub
    --order NAME          alpha (default) | makemd (manual order from the
                          make.md plugin's .space/context.mdb)
    --ignore EXT[,EXT..]  drop embeds of these media types, e.g. "png,mp3"
    --no-cover            skip the cover page
    -v, --verbose         progress info

## What it does with a folder

Notes merge into one PDF: each file name becomes a heading, headings inside
the file shift one level down; subfolders become nested sections; a folder
note (`X/X.md`) renders as the section intro. Frontmatter is stripped,
`![[image]]` embeds are resolved vault-wide, remote images are downloaded at
export time, YouTube/note embeds render as styled references, and fenced code
blocks get Pygments syntax highlighting.
