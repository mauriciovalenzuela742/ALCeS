# ptf_ic_icbl_hosts_modjaz20 (Modjaz+20, arXiv:1901.00872)

- No está en VizieR: se usa la fuente LaTeX del paper (título verificado). Se leen la tabla 2 (tab:emission: región de la apertura y z) y la tabla 4 (tab:PTFZ: metalicidades de pyMCZ).
- **48 hosts** = 14 Ic-BL + 28 Ic + 6 "weird/uncertain", igual al paper. PTF12gzk ("Ic-peculiar") se asigna a Ic, así que quedan 29 Ic. Los otros 5 de "weird/uncertain" quedan como SN-other.
- oh12 = PP04_O3N2 en 46 hosts. Si falta, se usa M08 N2Ha (2 hosts: 10qqd y 10yow).
- oh12_type:
  - **host_local** si la región es "SNsite" (40 hosts);
  - `unknown` si es nuc o HII lejos del sitio (8 hosts, incluido 12hvv, que viene de SDSS).
  - La sección 3 del paper confirma que la apertura se centra en la región HII más cercana al sitio de la SN. La metalicidad es **local**; en sources.csv figuraba `unknown`.
- El E(B-V)_host de la tabla 4 es del gas (decremento de Balmer), no de la línea de visión de la SN, así que no se copia.
- Errata corregida: PTF12gzk tiene z=0.148 en `tab:emission`, una fila que el `.tex` dice haber insertado a mano. Schulze+21 da z=0.01377 para el mismo host, y Modjaz+20 lo describe como el host menos luminoso de la muestra (M*=10^6.95 M☉), lo que no cuadra con z=0.148. El script lo reemplaza por 0.0138 (`Z_FIX`).
- La fuente no trae fotometría ni espectros de la SN.
