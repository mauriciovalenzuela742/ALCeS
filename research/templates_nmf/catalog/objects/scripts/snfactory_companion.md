# snfactory_companion: SALTADA (sin part CSV)

Paper: arXiv:2005.03462, "The SNEMO and SUGAR Companion Datasets" (título verificado en
arxiv.org; PDF leído). Tabla 1 del paper: SNEMO companion (NewYork-Alleg) 171 SNe Ia y
2485 espectros; SUGAR companion (NewMexico-Caballo) 172 SNe Ia y 2187 espectros; 133 en común.
Los datos están en VizieR J/ApJ/869/167 (SNEMO, Saunders+18) y J/A+A/636/A46 (SUGAR, Léget+20).

## Por qué no hay inventario por objeto
- Las tablas por objeto existen (lista de espectros con fase por SN en J/ApJ/869/167/list;
  número de espectros por SN en J/A+A/636/A46/features), pero **los nombres están cegados**:
  `Test_SN0`, `SN-training-1`, `SN-validation-3`... (verificado con asu-tsv en el espejo
  vizier.idia.ac.za). La tabla de coeficientes de snfactory.lbl.gov/snemo
  (`AllCoeffs_machinereadabletable.txt`) usa la misma columna `SNName`.
- Sin nombre real, RA/Dec ni z, las filas no se pueden unir con `snfactory_hosts`, CfA, etc.;
  `viability.py` las contaría como objetos nuevos y duplicaría SNe que ya están en otras
  fuentes. Además el paper dice que los espectros están llevados al reposo (z = 0) y con
  magnitud absoluta cegada.
- Conclusión: útil como conjunto de entrenamiento de espectros (contar a nivel de fuente:
  ~210 SNe distintas), no para el inventario por objeto. Pendiente: pedir a SNfactory la
  tabla de correspondencia de nombres (no se pidió; sería `on_request`).
