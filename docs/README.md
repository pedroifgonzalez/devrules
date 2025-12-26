# Documentation

This directory contains the MkDocs-based documentation for DevRules.

## Local Development

### Installation

Install the docs dependencies:

```bash
pip install -e ".[docs]"
```

### Preview

To preview the documentation locally:

```bash
mkdocs serve
```

This will start a local server at `http://127.0.0.1:8000/`

### Build

To build the documentation:

```bash
mkdocs build --strict
```

The built site will be in the `site/` directory.

### Testing

- Test multi-audience navigation by browsing sections: Overview, For Developers, For Decision Makers, Enterprise
- Test search functionality
- Check internal links

### Adding New Pages

- Place new markdown files in the appropriate subdirectory (docs/overview/, docs/developers/, etc.)
- Add front matter if needed (title, description, tags)
- Update the index.md in the section if necessary
- For navigation ordering, update the .pages file in the subdirectory
