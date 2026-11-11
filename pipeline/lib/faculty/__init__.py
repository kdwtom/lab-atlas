from . import (dgist, dgist_tracks, gist, gist_depts, hanyang, kaist, kaist_depts, korea, postech, skku, snu, snu_depts,
               sogang, unist, yonsei)

# parser name (departments.yaml) -> collect(client, dept)
PARSERS = {
    "kaist_bio": kaist.collect,
    "snu_bio": snu.collect,
    "postech_dir": postech.collect,
    "unist_dir": unist.collect,
    "gist_cms": gist.collect,
    "dgist_cards": dgist.collect,
    "kaist_chem": kaist_depts.collect_chem,
    "kaist_phys": kaist_depts.collect_phys,
    "kaist_math": kaist_depts.collect_math,
    "kaist_cs": kaist_depts.collect_cs,
    "snu_cms": snu_depts.collect_cms,
    "snu_math": snu_depts.collect_math,
    "snu_cse": snu_depts.collect_cse,
    "gist_phys": gist_depts.collect_phys,
    "dgist_cms_track": dgist_tracks.collect_cms_track,
    "dgist_site_track": dgist_tracks.collect_site_track,
    # phase 3
    "yonsei_cards": yonsei.collect_cards,
    "yonsei_chem": yonsei.collect_chem,
    "yonsei_phys": yonsei.collect_phys,
    "yonsei_cs": yonsei.collect_cs,
    "korea_cms": korea.collect,
    "skku_cards": skku.collect,
    "hanyang_liferay": hanyang.collect,
    "sogang": sogang.collect,
}
