"""Model the worker's next tick after Firestore exhausts contention retries."""
from google.api_core.exceptions import Aborted

def attempt(operation, ref):
    try:
        operation(ref)
    except ValueError as exc:
        if not isinstance(exc.__cause__,Aborted):raise
        # Caller retries remaining jobs after the concurrent wave, just as tick does.
    except Aborted:
        pass
