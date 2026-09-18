from pathlib import Path
from importlib import import_module
import inspect

SCRAPER_REGISTRY = {}

SPECIAL_NAMES = {
    "motor1_tr": "Motor1TR",
    "insideevs": "InsideEVs",
    "carbuzz": "CarBuzz",
    "autoexpress": "AutoExpress",
    "autoevolution": "Autoevolution",
    "greencarreports": "GreenCarReports",
    "motorauthority": "MotorAuthority",
    "cleantechnica": "CleanTechnica",
    "automotivenews": "AutomotiveNews",
    "autocarindia": "AutocarIndia",
    "drivespark": "DriveSpark",
    "donanimhaber": "DonanimHaber",
    "cnevpost": "CNEVPost",
    "log": "LOG",
    "motor1_tr": "Motor1TR",
}


def make_name(filename: str) -> str:
    filename = filename.lower()

    if filename in SPECIAL_NAMES:
        return SPECIAL_NAMES[filename]

    return "".join(part.capitalize() for part in filename.split("_"))


def register_folder(folder: str):

    base = Path(__file__).parent / folder

    if not base.exists():
        return

    for file in sorted(base.glob("*.py")):

        if file.stem.startswith("_"):
            continue

        if file.stem == "common":
            continue

        module_name = f"app.scrapers.{folder}.{file.stem}"

        try:
            module = import_module(module_name)

        except Exception as e:
            print(f"❌ Import Hatası: {module_name}")
            print(e)
            continue

        scraper_name = getattr(
            module,
            "SCRAPER_NAME",
            make_name(file.stem),
        )

        scraper_type = getattr(
            module,
            "SCRAPER_TYPE",
            folder,
        )

        scraper_func = None

        for name, obj in inspect.getmembers(module, inspect.isfunction):

            if name.startswith("get_") and name.endswith("_news"):
                scraper_func = obj
                break

        if scraper_func is None:
            print(f"⚠ Scraper bulunamadı: {module_name}")
            continue

        if scraper_name in SCRAPER_REGISTRY:
            old = SCRAPER_REGISTRY[scraper_name]["type"]

            print(
                f"⚠ Aynı scraper bulundu: "
                f"{scraper_name} ({old} -> {scraper_type})"
            )

        SCRAPER_REGISTRY[scraper_name] = {
            "name": scraper_name,
            "type": scraper_type,
            "folder": folder,
            "module": module_name,
            "function": scraper_func,
        }

        # Windows'un varsayılan konsol kodlaması Unicode simgeleri her zaman
        # yazamaz. Kayıt mesajı uygulamanın başlamasını engellememelidir.
        print(
            f"[OK] {scraper_name:<20} "
            f"[{scraper_type}]"
        )


register_folder("rss")
register_folder("html")
register_folder("browser")

from app.scrapers.rss.common import read_rss

SCRAPER_REGISTRY["RSS"] = {
    "name": "RSS",
    "type": "rss",
    "folder": "rss",
    "module": "app.scrapers.rss.common",
    "function": read_rss,
}


def get_scraper(name: str):
    item = SCRAPER_REGISTRY.get(name)

    if item:
        return item["function"]

    return None


def get_scraper_info(name: str):
    return SCRAPER_REGISTRY.get(name)


def get_scraper_names():
    return sorted(SCRAPER_REGISTRY.keys())


def get_all_scrapers():
    return SCRAPER_REGISTRY


if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("AUTO SCRAPER REGISTRY")
    print("=" * 70)

    print(f"Toplam Scraper : {len(SCRAPER_REGISTRY)}")

    print("-" * 70)

    for name in sorted(SCRAPER_REGISTRY):

        info = SCRAPER_REGISTRY[name]

        print(
            f"{info['name']:<20}"
            f"{info['type']:<10}"
            f"{info['module']}"
        )

    print("=" * 70)
