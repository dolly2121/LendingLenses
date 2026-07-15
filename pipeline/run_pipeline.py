"""Orchestrates the batch pipeline: Bronze then Silver. `make pipeline` and
`make demo` both call this. Gold joins the sequence in Phase 4."""
from pipeline import bronze, silver


def main() -> None:
    bronze.main()
    silver.main()


if __name__ == "__main__":
    main()
