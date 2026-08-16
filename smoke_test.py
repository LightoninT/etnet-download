"""Live smoke test: fetch the etnet futures page, parse it, write an .xlsx."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import downloader, excel_writer  # noqa: E402


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/etnet_test")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1) fetch default page (HSI front month) ...")
    page = downloader.get_futures_page()
    print("   contract:", page.contract_name, page.subtype, page.month)
    print("   update_time:", page.update_time)
    print("   sessions:", [(s.session, s.last, s.change, s.premium) for s in page.sessions])
    print("   open_interest:", page.open_interest)
    print("   spot:", page.spot)
    print("   interval rows:", len(page.interval), "->", page.interval[:2])

    assert page.sessions, "no session quotes parsed"
    assert page.open_interest is not None, "no open interest parsed"
    assert page.spot is not None, "no spot parsed"
    assert len(page.interval) > 0, "no interval table parsed"

    wb = excel_writer.build_workbook(page)
    p1 = out_dir / "single.xlsx"
    wb.save(str(p1))
    print("   saved:", p1)

    print("2) fetch a specific contract (HTI 202609) ...")
    page2 = downloader.get_futures_page("HTI", "202609")
    print("   contract:", page2.contract_name, "sessions:", len(page2.sessions),
          "interval:", len(page2.interval))

    print("3) fetch all front-month contracts ...")
    html = downloader.fetch_html()
    opts = downloader.front_month_options(html)
    print("   front-month options:", opts)
    pages = []
    for code, month, label in opts[:3]:   # test with a subset to stay quick
        print("   fetching", label, code, month)
        pages.append(downloader.get_futures_page(code, month))
    wb2 = excel_writer.build_multi_workbook(pages)
    p2 = out_dir / "multi.xlsx"
    wb2.save(str(p2))
    print("   saved:", p2)
    print("OK")


if __name__ == "__main__":
    main()
