# ztf_bts

- Datos: CSV del BTS Sample Explorer (`explorer.php?f=s&subsample=sn&format=csv`, con RA, Dec, z y pico). Se descargó el 2026-10-27 y se guarda en `raw/ztf_bts/bts_explorer_sn.csv`; el script lo reutiliza (hay que borrarlo para refrescar).
- Resultado: **11 484 SNe clasificadas.** `sources.csv` dice 11 431 SNe por debajo de mag 19 según la página. El CSV del subsample `sn` no aplica corte de magnitud (el pico llega a 19.72) ni de calidad; con `quality=y` y `endpeakmag=19.0` salen 7 087. Se deja el subsample completo.
- Tipos: mapeo directo de los tipos del BTS al esquema (Ia-pec y Ia-SC → Ia-other; II-pec → II; IIn-pec → IIn; Ib-pec → Ib; Ic-pec → Ic; Ca-rich-Ca → Ca-rich). Las 42 `SN Ib/c` quedan como `SN-other`, porque son ambiguas.
- `z_type=unknown`: el explorer no distingue el z del host del de la SN. Mientras no se precise, ningún objeto que solo esté en el BTS pasa el nivel `foto` de viability.
- No hay bandas, puntos ni espectros por objeto. La fotometría sale de ZTF (forced photometry o brokers) y los espectros, de TNS o WISeREP. La columna `A_V` (extinción galáctica) no se convierte a E(B−V) porque el explorer no indica R_V.
- Se solapa con `ztf_bts_snii_hinds25` (mismos ZTFID).
