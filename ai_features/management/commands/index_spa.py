from django.core.management.base import BaseCommand, CommandError

from ai_features.config import enabled


class Command(BaseCommand):
    help = "Incrementally index public Spa documents, only after separate indexing and provider approval."

    def handle(self, *args, **options):
        from ai_features.config import option
        if not enabled("AI_RAG_ENABLED") or not enabled("AI_RAG_INDEX_UPDATE_APPROVED"):
            raise CommandError("RAG indexing/update has not been approved.")
        provider = option("AI_PROVIDER", "mock")
        if provider not in {"gemini", "mock"}:
            raise CommandError("Only Gemini or internal mock indexing is allowed.")
        if provider == "gemini":
            if not enabled("AI_GEMINI_REQUESTS_APPROVED") or not enabled("AI_GEMINI_FREE_TIER_CONFIRMED"):
                raise CommandError("Gemini free-tier requests have not been approved.")
        from ai_features.rag import public_documents, vector_index
        changed = vector_index().sync(public_documents())
        self.stdout.write(self.style.SUCCESS(f"Indexed {changed} changed public documents; unchanged vectors retained."))
