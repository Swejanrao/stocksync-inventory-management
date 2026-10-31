import click

from app.extensions import db
from app.seed import seed_database


def register_commands(app):

    @app.cli.command("init-db")
    def init_db():
        """Create missing database tables without deleting existing data."""
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("seed")
    def seed():
        """Insert safe starter records."""
        try:
            result = seed_database()
            click.echo("Starter data inserted or already present.")
            click.echo(result)
        except Exception as exc:
            db.session.rollback()
            click.echo(f"Seed failed: {exc}")
            raise

    @app.cli.command("db-status")
    def db_status():
        """Display basic database record counts."""
        from app.models import (
            Product,
            SKU,
            Location,
            InventoryBalance,
            InventoryMovement,
            CustomerOrder,
        )

        click.echo(f"Products: {Product.query.count()}")
        click.echo(f"SKUs: {SKU.query.count()}")
        click.echo(f"Locations: {Location.query.count()}")
        click.echo(
            f"Inventory balances: {InventoryBalance.query.count()}"
        )
        click.echo(
            f"Movements: {InventoryMovement.query.count()}"
        )
        click.echo(f"Orders: {CustomerOrder.query.count()}")
