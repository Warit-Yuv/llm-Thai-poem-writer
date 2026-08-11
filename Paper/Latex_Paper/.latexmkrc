# Force XeLaTeX so Thai script renders in iSAI-Klon-Checker.tex
# (read by latexmk when run from this folder)
$pdf_mode = 4;              # 4 = xelatex
$postscript_mode = undef;
$dvi_mode = undef;
$xelatex = 'xelatex -interaction=nonstopmode -halt-on-error %O %S';
$bibtex_use = 1;
