# taddia16_iptf_snii_metallicity

- Datos: tablas `tab:spectra` y `tab:metal` del fuente LaTeX de arXiv:1602.01433 (título verificado, "Metallicity from Type II Supernovae from the (i)PTF"). No hay catálogo en VizieR ni datos aparte.
- Resultado: **39 SNe (34 IIP y 5 IIL), igual que el abstract ("39 (i)PTF SNe II").** Cada una tiene un espectro (el que se usa para pEW 5018) con su fase desde la explosión (28–116 d).
- **No se llena `oh12`.** El paper da la metalicidad como Z/Z☉ (host global por LZ y LCZ, O3N2 solo para 7 hosts, y Z en el sitio de la SN extrapolada con un gradiente fijo). No dice qué valor solar usó, así que convertir a 12+log(O/H) sería inventar. Si se acepta un valor solar, el dato está en `tab:metal`, que el script ya descarga.
- No hay z, coordenadas de la SN (solo del host), fotometría ni extinción por objeto. La fuente casi no aporta al conteo de viability; sirve para identificar SNe IIP de baja Z en PTF.
- Nombres: la tabla abrevia (`09ecm`). Se reconstruye `PTF09ecm` (2009–2012) o `iPTF13aaz` (2013–2014) según la convención de PTF/iPTF.
