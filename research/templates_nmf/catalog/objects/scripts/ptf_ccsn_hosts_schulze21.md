# ptf_ccsn_hosts_schulze21 (Schulze+21, github.com/steveschulze/PTF)

- Archivo: catalog/PTF_CCSN.fits (2,9 MB, commit e71df08). La extensión "General" tiene **888 objetos**, igual al paper.
- **No trae metalicidad.** Solo trae la fotometría del host (no de la SN) y, de Prospector, la masa, SFR, sSFR, edad y E(B-V)* estelar. Por eso oh12, bands, n_phot y n_spec quedan vacíos. Para NMF sirve por el tipo, el z y la posición, que permiten cruzar con otras fuentes de PTF.
- Tipos:

  | Tipo en la fuente | subclass | SNe |
  |---|---|---|
  | SNII | II | 498 |
  | SNIIn | IIn | 111 |
  | SNIIb | IIb | 61 |
  | SNIc | Ic | 60 |
  | SNIb | Ib | 46 |
  | SLSN-I | SLSN-I | 36 |
  | SNIc-BL | Ic-BL | 36 |
  | SLSN-IIn, SLSN-IIb, SLSN-II | SLSN-II | 16 |
  | SNIbn | Ibn | 9 |
  | SNIbc y candidatos cSLSN-I, cSLSN-IIn | SN-other | 15 |

- z_type:

  | ZMETHOD | z_type | SNe |
  |---|---|---|
  | GAL.LINES | host_spec | 333 |
  | MATCHING | spec | 158 |
  | SDSS, NED | unknown | 397 |

  SDSS y NED quedan en unknown porque el README no dice si esos z son espectroscópicos.
- alt_names = IAU_NAME (199 objetos lo tienen).
- El script lee el FITS con astropy, que está instalado en el python del sistema.
