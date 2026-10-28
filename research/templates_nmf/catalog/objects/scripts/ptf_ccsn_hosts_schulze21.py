"""Inventario por objeto de Schulze+21 (hosts de 888 CCSN de PTF, repo steveschulze/PTF).

catalog/PTF_CCSN.fits, extension 1 ("General"): OBJECT, TYPE, REDSHIFT, ZMETHOD, IAU_NAME,
SN_RA_HMS, SN_DEC_DMS (ver catalog/README.md del repo).
El catalogo NO trae metalicidad (solo masa, SFR, sSFR, edad y E(B-V)* estelar de Prospector
en la extension 3) ni fotometria/espectros de la SN (la fotometria es del host), asi que
oh12, bands, n_phot y n_spec quedan vacios.
z_type: GAL.LINES -> host_spec (lineas del host en el espectro de la SN); MATCHING -> spec
(ajuste de templates al espectro de la SN); SDSS y NED -> unknown (el README no dice si es
z espectroscopico o fotometrico).
Tipos: el prefijo 'c' (cSLSN-I, cSLSN-IIn) son candidatos -> SN-other; SNIbc -> SN-other;
SLSN-IIn y SLSN-IIb -> SLSN-II.
Se fija el commit del repo usado.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "ptf_ccsn_hosts_schulze21"
SHA = "e71df08a8c8ec05bce2b292c6105910249f662c0"  # master al 2026-10-27
URL = f"https://raw.githubusercontent.com/steveschulze/PTF/{SHA}/catalog/PTF_CCSN.fits"

TYPE_MAP = {
    "SNII": "II", "SNIIn": "IIn", "SNIIb": "IIb", "SNIb": "Ib", "SNIc": "Ic",
    "SNIc-BL": "Ic-BL", "SNIbn": "Ibn", "SNIbc": "SN-other",
    "SLSN-I": "SLSN-I", "SLSN-II": "SLSN-II", "SLSN-IIn": "SLSN-II", "SLSN-IIb": "SLSN-II",
    "cSLSN-I": "SN-other", "cSLSN-IIn": "SN-other",
}
ZTYPE = {"GAL.LINES": "host_spec", "MATCHING": "spec", "SDSS": "unknown", "NED": "unknown"}


def s(v):
    if isinstance(v, bytes):
        v = v.decode()
    return str(v).strip()


def main():
    from astropy.table import Table  # astropy esta instalado en el python del sistema

    d = u.raw_dir(SID)
    path = u.fetch(URL, os.path.join(d, "PTF_CCSN.fits"))
    t = Table.read(path, hdu=1)
    rows = []
    for r in t:
        iau = s(r["IAU_NAME"])
        ra = s(r["SN_RA_HMS"]).replace(" ", ":").split(":")
        de = s(r["SN_DEC_DMS"]).replace(" ", ":").split(":")
        row = dict(sn_name=s(r["OBJECT"]), subclass=TYPE_MAP[s(r["TYPE"])],
                   z=u.fmt(float(r["REDSHIFT"]), 5), z_type=ZTYPE[s(r["ZMETHOD"])])
        if iau and "..." not in iau and iau.lower() not in ("nan", "--", "none", "-"):
            row["alt_names"] = iau if iau.upper().startswith("SN") else f"SN {iau}"
        if len(ra) == 3 and len(de) == 3:
            sign = "-" if de[0].startswith("-") else "+"
            row["ra"] = u.fmt(u.sexa_ra(*ra), 5)
            row["dec"] = u.fmt(u.sexa_dec(sign, de[0].lstrip("+-"), de[1], de[2]), 5)
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
