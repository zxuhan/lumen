import uuid

from app.db import SessionFactory
from app.services import runs, tools


async def run_tool(_: dict, run_id: uuid.UUID) -> None:
    async with SessionFactory() as session:
        try:
            run = await runs.load(session, run_id)
        except runs.RunNotFound:
            return
        # Queue redelivery or reprocessing after a worker restart must not be billed twice
        if run.status.is_terminal:
            return

        await tools.execute(session, run)
