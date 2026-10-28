# aamer25_slsn_spectra (Aamer+25, arXiv:2503.21874)

- Los espectros procesados están en el mismo repo gmzsebastian/SLSNe, en supernovae/<SN>/processed_spectra/. El README pide citar Aamer+25 por ellos.
- No se bajan los espectros: supernovae/ pesa unos 590 MB. El script los cuenta desde el árbol de la API de GitHub, fijado al commit de raw/aamer25_slsn_spectra/commit.txt.
- El repo tiene **873 espectros procesados de 233 SNe**; el abstract (título verificado) dice **974 de 234**. raw_spectra tiene 1572 espectros de 236 SNe. No resolví la diferencia.
- 2022vxc tiene 4 espectros pero no está en sne_data.txt, así que queda sin z ni fase.
- z, ebv_mw y Peak salen de sne_data.txt (Gomez+24).
- Fase = (fecha en el nombre del archivo - Peak)/(1+z), con resolución de un día.
