# anderson16_snii_hii_metallicity

- No existe catálogo en VizieR. Las tablas se leen del apéndice en el fuente LaTeX de arXiv:1602.00011: la Tabla A.1 da la velocidad del host (NED) y el tipo, y la Tabla B.2 (`hiilist`) las abundancias O/H.
- Resultado: 119 SNe con 12+log(O/H) local. **Coincide con las "119 regiones HII" de la nota de la fuente.** Hay 115 II, 3 IIb (2007am, 2007ay, 2008gq) y 1 IIn (2006qq). El texto habla de "un par de IIn", pero la tabla marca solo una.
- oh12 = M13 N2 (calibración `N2_M13`), entre 8.03 y 8.76. La tabla también trae M13 O3N2 y PP04 N2/O3N2, que no se copian. 23 SNe tienen la abundancia tomada de Anderson+10 (marca `*` en B.2), y 2005dn es un límite superior según el caption.
- No hay fotometría ni espectros de SN (`n_phot` y `n_spec` vacíos). La fuente aporta la metalicidad, y el cruce por nombre la une con Gutiérrez+17, Anderson+24 y Galbany+16.
