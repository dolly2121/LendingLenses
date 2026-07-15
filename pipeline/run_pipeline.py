"""Orchestrates the batch pipeline: Bronze, Silver, Gold. `make pipeline` and
`make demo` both call this."""
from pipeline import bronze, silver, gold


def main() -> None:
    bronze.main()
    silver.main()
    gold.main()


if __name__ == "__main__":
    main()
