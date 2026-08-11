# Force XeLaTeX so Thai script renders in iSAI-Klon-Checker.tex
# (read by latexmk locally and by Overleaf at the project root)
$pdf_mode = 4;              # 4 = xelatex
$postscript_mode = undef;
$dvi_mode = undef;
$xelatex = 'xelatex -interaction=nonstopmode -halt-on-error %O %S';
$bibtex_use = 1;
