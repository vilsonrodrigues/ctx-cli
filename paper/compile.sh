#!/bin/bash
# Compile paper from markdown sections to PDF
# Usage: ./paper/compile.sh

set -e

PAPER_DIR="$(dirname "$0")"
OUTPUT_DIR="$PAPER_DIR/output"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Paper Compilation ===${NC}"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check dependencies
echo -e "\n${BLUE}Checking dependencies...${NC}"

if ! command -v pandoc &> /dev/null; then
    echo -e "${RED}Error: pandoc not found${NC}"
    echo "Install: sudo apt install pandoc texlive-full"
    exit 1
fi

echo -e "${GREEN}✓ pandoc found${NC}"

# Concatenate all sections
echo -e "\n${BLUE}Concatenating sections...${NC}"
cat "$PAPER_DIR"/0*.md "$PAPER_DIR/references.md" > "$OUTPUT_DIR/full-paper.md"
echo -e "${GREEN}✓ Created full-paper.md${NC}"

# Convert to LaTeX
echo -e "\n${BLUE}Converting to LaTeX...${NC}"
pandoc "$OUTPUT_DIR/full-paper.md" \
    -s \
    --number-sections \
    --toc \
    -V documentclass=article \
    -V geometry:margin=1in \
    -V fontsize=11pt \
    -o "$OUTPUT_DIR/full-paper.tex"
echo -e "${GREEN}✓ Created full-paper.tex${NC}"

# Convert to PDF (if pdflatex available)
if command -v pdflatex &> /dev/null; then
    echo -e "\n${BLUE}Converting to PDF...${NC}"
    cd "$OUTPUT_DIR"
    pdflatex -interaction=nonstopmode full-paper.tex > /dev/null 2>&1 || true
    pdflatex -interaction=nonstopmode full-paper.tex > /dev/null 2>&1 || true
    cd - > /dev/null

    if [ -f "$OUTPUT_DIR/full-paper.pdf" ]; then
        echo -e "${GREEN}✓ Created full-paper.pdf${NC}"

        # Create timestamped copy
        cp "$OUTPUT_DIR/full-paper.pdf" "$OUTPUT_DIR/paper_${TIMESTAMP}.pdf"
        echo -e "${GREEN}✓ Saved copy: paper_${TIMESTAMP}.pdf${NC}"
    else
        echo -e "${RED}! PDF generation had warnings (check .log)${NC}"
    fi
else
    echo -e "${BLUE}ℹ pdflatex not found, skipping PDF generation${NC}"
fi

# Convert to HTML (for preview)
echo -e "\n${BLUE}Converting to HTML...${NC}"
pandoc "$OUTPUT_DIR/full-paper.md" \
    -s \
    --toc \
    --number-sections \
    --css=https://latex.now.sh/style.css \
    -o "$OUTPUT_DIR/full-paper.html"
echo -e "${GREEN}✓ Created full-paper.html${NC}"

# Word count
echo -e "\n${BLUE}Statistics:${NC}"
WORD_COUNT=$(wc -w < "$OUTPUT_DIR/full-paper.md")
echo "Word count: $WORD_COUNT words"
echo "Target: ~5000-7000 words for 10-page paper"

# Section breakdown
echo -e "\n${BLUE}Section sizes:${NC}"
for file in "$PAPER_DIR"/0*.md; do
    section=$(basename "$file" .md)
    words=$(wc -w < "$file")
    printf "%-20s %5d words\n" "$section" "$words"
done

echo -e "\n${GREEN}=== Compilation Complete ===${NC}"
echo "Files created in: $OUTPUT_DIR"
echo ""
echo "View HTML: xdg-open $OUTPUT_DIR/full-paper.html"
echo "View PDF:  xdg-open $OUTPUT_DIR/full-paper.pdf"
