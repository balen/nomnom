import random

import djclick as click
from django.db.models import Count, Q
from nominate import models
from nominate.admin import NominatingMemberFilter
from nominate.models import Category, Election


@click.command()
@click.argument("election_id")
@click.argument("voter_count", default=5, type=int)
def main(election_id: str, voter_count: int):
    election = Election.objects.get(slug=election_id)

    # find a member that doesn't have any ranks for the selected election
    profiles_without_rank = models.NominatingMemberProfile.objects.annotate(
        rank_count=Count(
            "rank", filter=Q(rank__finalist__category__election=election), distinct=True
        )
    ).filter(rank_count=0)

    print(f"We have {profiles_without_rank.count()} members without ranks")

    for i in range(voter_count):
        fake_ballot(election, profiles_without_rank[i])


CATEGORY_VOTE_PROBABILITY = 0.99
FINALIST_VOTE_PROBABILITY = 0.90


def fake_ballot(election: Election, member: NominatingMemberFilter):
    for category in Category.objects.filter(election=election):
        if random.random() > CATEGORY_VOTE_PROBABILITY:
            continue
        finalists = list(category.finalist_set.all())
        random.shuffle(finalists)
        selected_finalists = [
            f for f in finalists if random.random() < FINALIST_VOTE_PROBABILITY
        ]
        for i, finalist in enumerate(selected_finalists):
            models.Rank(membership=member, finalist=finalist, position=i + 1).save()

    print("Submitted ballot")
