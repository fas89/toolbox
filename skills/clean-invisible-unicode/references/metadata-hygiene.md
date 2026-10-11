# File metadata hygiene

Character-level cleaning does nothing to file metadata. If the user's actual concern is
*"what does this file leak about me before I share it"*, that is this page — a different
problem with different tools.

## What leaks

| Container | Typical leak |
| --- | --- |
| JPEG / HEIC / TIFF | EXIF GPS coordinates, camera body + lens serial number, capture timestamp, owner name |
| PNG / WebP | XMP packets, `tEXt` chunks, editing-tool identifiers |
| PDF | `/Author`, `/Creator`, `/Producer`, XMP, revision history, sometimes cropped-but-present content |
| DOCX / XLSX / PPTX | `docProps/core.xml` author and last-modified-by, tracked changes, comments, `customXml` |
| ODT | `meta.xml` generator, editing cycles, total editing time |
| SVG | editor `<metadata>`, `<title>`/`<desc>`, absolute source paths |
| HTML | `<meta name="generator">`, JSON-LD blocks, absolute local paths in comments |

GPS in a photo and an author name in a PDF are the two that most often surprise people.

## Inspect first

```bash
exiftool -a -G1 -s FILE          # everything, grouped, with tag names
exiftool -gps:all -author -creator FILE
```

For Office files, the metadata is just XML inside a zip:

```bash
unzip -p report.docx docProps/core.xml
```

For PDFs:

```bash
pdfinfo report.pdf
exiftool -a -G1 report.pdf
```

## Strip

```bash
exiftool -all= -overwrite_original_in_place FILE      # images
exiftool -all= -o cleaned.pdf report.pdf              # PDF, to a new file
qpdf --linearize --replace-input cleaned.pdf          # rebuild PDF structure
```

`exiftool -all=` on a PDF marks the old metadata as free rather than removing the bytes —
`qpdf` is what actually rebuilds the file without them. Verify after either step:

```bash
exiftool -a -G1 cleaned.pdf | grep -Ei 'author|creator|producer|gps'
```

For Office documents, strip via the document properties panel in the application, or rewrite
the zip with `docProps/core.xml` emptied. Word's *Inspect Document → Remove All* is more
thorough than editing the XML by hand, because it also clears tracked changes and comments.

## Two cautions

**Re-encoding is lossy.** Stripping metadata by re-saving a JPEG re-compresses it. Prefer
`exiftool -all=`, which rewrites only the metadata segments.

**Metadata is also provenance.** The same operation that removes a GPS coordinate removes
C2PA Content Credentials and generator tags. Those exist so downstream viewers can tell
where a file came from, and for synthetic media that disclosure is often the point. Removing
them for privacy before sharing your own photo is ordinary hygiene; removing them so a
generated image reads as authentic is not, and this skill is not the tool for it.

If a file carries Content Credentials, say so rather than silently dropping them:

```bash
c2patool FILE                    # prints the manifest if one is present
```
