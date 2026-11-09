from django.core.management.base import BaseCommand

from analytics import queries


def _pct(rate):
    return "n/a" if rate is None else f"{rate:.1%}"


class Command(BaseCommand):
    help = "Print the North Star and D30 retention metrics."

    def handle(self, *args, **options):
        d30 = queries.d30_retention()
        self.stdout.write(f"Plants harvested (North Star): {queries.north_star()}")
        self.stdout.write(f"Harvest success rate: {_pct(queries.harvest_success_rate())}")
        self.stdout.write(f"D30 retention: {_pct(d30['rate'])} ({d30['retained']}/{d30['cohort']} users)")
