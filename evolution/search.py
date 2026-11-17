"""Search policies. The board loop calls these and does not know the details.

heavy: the EA, except each child draws a flip count from a power law and then
flips each gene with probability count/N. Small counts are common.

tworate: the EA, except half the children flip at half the current rate and
half at double. The next rate is whichever of those two produced the better
child. A tie keeps the higher rate. The stored rate stays between 1 and N/2.

ea: a population. The top elites are copied. Every other slot is one child of
two fitness-proportional parents, crossed over by section, then mutated.

inchworm: the same loop, with 5 elites in a population of 20 and a base rate of
one flip. After the best score has held for 5 generations, the 5 children
whose parents score lowest get a larger mutation. That rate grows by 4 flips
every 3 further generations at the same score, up to 40, and returns to one
flip when the best score rises.

hill: each genome climbs alone. A step mutates that one genome, and the mutant
replaces it when the accept rule says so. Population 1 starts from the damaged
genome. A larger population starts from the damaged genome plus mutants of it.
There is no crossover and no competition between climbers.

bandit: the same population, elites, and section crossover as the EA. Each
child then flips an exact number of genes. uniform draws those genes from the
whole genome. ucb draws sections until they can hold the flips, scores the
crossover child, flips, scores the mutant, and updates only the sections that
were flipped. The bandit reward is impact, not the fitness used to select
survivors. Both modes start from the same exact-flip initial population.
"""

from __future__ import annotations

from functools import lru_cache

from analysis.tile_genome import breed, flip_exact, mate, mutate
from evolution.bandit import impact_reward, realized_flips

INCHWORM_POPULATION = 20
INCHWORM_ELITES = 5
INCHWORM_BASE_FLIPS = 1
INCHWORM_STUCK_GENERATIONS = 5
INCHWORM_BOOST_EVERY = 3
INCHWORM_BOOST_FLIPS = 4
INCHWORM_MAX_FLIPS = 40
INCHWORM_BOOST_COUNT = 5
HEAVY_BETA = 1.5


def initial_exact(damaged, population: int, rng, n_flips: int):
    """One damaged genome, then exact-count mutants of it.

    uniform and ucb both use this, with the same seed, before either mode
    draws a bandit arm. Generation 0 therefore matches.
    """
    if n_flips > len(damaged):
        raise SystemExit(f"cannot flip {n_flips} genes in a genome of {len(damaged)}")
    pop = [damaged]
    while len(pop) < population:
        indexes = rng.sample(range(len(damaged)), n_flips)
        pop.append(flip_exact(damaged, indexes))
    return pop


def initial_population(algorithm: str, damaged, population: int, rng, probability):
    """One damaged genome, then mutants of it until the population is full.

    A hill climber with population 1 is just the damaged genome. A larger hill
    population uses the same start as the EA: the damaged genome plus mutants.
    """
    del algorithm
    pop = [damaged]
    while len(pop) < population:
        pop.append(mutate(damaged, rng, probability))
    return pop


def ea_next(pop, scores, sections, rng, probability, share, elites):
    """Return the next population and the elite genomes whose scores carry forward."""
    ranked = sorted(range(len(pop)), key=lambda i: scores[i], reverse=True)
    carried = {pop[i]: scores[i] for i in ranked[:elites]}
    nxt = [pop[i] for i in ranked[:elites]]
    while len(nxt) < len(pop):
        nxt.append(breed(pop, scores, sections, rng, probability, share))
    return nxt, carried


@lru_cache(maxsize=4)
def _power_law_cdf(n: int, beta: float) -> tuple[float, ...]:
    weights = [i ** (-beta) for i in range(1, n + 1)]
    total = sum(weights)
    cdf = []
    acc = 0.0
    for weight in weights:
        acc += weight / total
        cdf.append(acc)
    cdf[-1] = 1.0
    return tuple(cdf)


def power_law_k(rng, n: int, beta: float = HEAVY_BETA) -> int:
    """Flip count from 1 to n. P(k) is proportional to k to the power -beta."""
    pick = rng.random()
    for k, threshold in enumerate(_power_law_cdf(n, beta), start=1):
        if pick <= threshold:
            return k
    return n


def heavy_mutate(genome, rng, beta: float = HEAVY_BETA):
    """One child mutation: draw k, then flip each gene with probability k/n."""
    k = power_law_k(rng, len(genome), beta)
    return mutate(genome, rng, k / len(genome)), k


def heavy_initial(damaged, population: int, rng):
    """Damaged genome, then heavy-tailed mutants of it."""
    pop = [damaged]
    strengths = []
    while len(pop) < population:
        child, strength = heavy_mutate(damaged, rng)
        pop.append(child)
        strengths.append(strength)
    return pop, strengths


def heavy_next(pop, scores, sections, rng, share, elites):
    """Elites copied. Every child is a section crossover, then a heavy-tailed mutation."""
    ranked = sorted(range(len(pop)), key=lambda i: scores[i], reverse=True)
    carried = {pop[i]: scores[i] for i in ranked[:elites]}
    nxt = [pop[i] for i in ranked[:elites]]
    strengths = []
    while len(nxt) < len(pop):
        child, _average = mate(pop, scores, sections, rng, share)
        mutated, strength = heavy_mutate(child, rng)
        nxt.append(mutated)
        strengths.append(strength)
    return nxt, carried, strengths


BANDIT_MIN_FLIPS = 1
BANDIT_MAX_FLIPS = 32


def clamp_bandit_rate(strength: float) -> float:
    """Keep a bandit's expected flip count between one flip and 32."""
    return min(BANDIT_MAX_FLIPS, max(BANDIT_MIN_FLIPS, strength))


def bandit_child_rates(n_children: int, strength: float) -> list[float]:
    """Half the children at half the current count, half at double. An odd child uses the lower count."""
    low = clamp_bandit_rate(strength / 2)
    high = clamp_bandit_rate(strength * 2)
    n_high = n_children // 2
    n_low = n_children - n_high
    return [low] * n_low + [high] * n_high


def adopt_bandit_rate(strengths, child_scores) -> float:
    """Move to the count whose children scored higher. A tie keeps the lower count."""
    best = {}
    for strength, score in zip(strengths, child_scores):
        if strength not in best or score > best[strength]:
            best[strength] = score
    if len(best) < 2:
        return clamp_bandit_rate(next(iter(best))) if best else BANDIT_MIN_FLIPS
    low, high = sorted(best)
    chosen = high if best[high] > best[low] else low
    return clamp_bandit_rate(chosen)


def clamp_strength(strength: float, n_bits: int) -> float:
    """Keep the stored rate between one flip and half the genome."""
    return min(n_bits / 2, max(1.0, strength))


def tworate_split(n_children: int, strength: float, n_bits: int):
    """Half the children at strength/2, half at 2*strength. An odd child uses the lower rate."""
    low = strength / 2
    high = min(strength * 2, float(n_bits))
    n_high = n_children // 2
    n_low = n_children - n_high
    return low, high, n_low, n_high


def adopt_tworate(strengths, child_scores, n_bits: int) -> float:
    """Move to the rate whose children scored higher. A tie keeps the higher rate."""
    best = {}
    for strength, score in zip(strengths, child_scores):
        if strength not in best or score > best[strength]:
            best[strength] = score
    if len(best) < 2:
        return clamp_strength(next(iter(best)), n_bits) if best else clamp_strength(1.0, n_bits)
    low, high = sorted(best)
    chosen = low if best[low] > best[high] else high
    return clamp_strength(chosen, n_bits)


def tworate_next(pop, scores, sections, rng, strength: float, share, elites):
    """Elites copied. Children split between half the current rate and double it."""
    ranked = sorted(range(len(pop)), key=lambda i: scores[i], reverse=True)
    carried = {pop[i]: scores[i] for i in ranked[:elites]}
    nxt = [pop[i] for i in ranked[:elites]]
    n_bits = len(pop[0])
    low, high, n_low, n_high = tworate_split(len(pop) - elites, strength, n_bits)
    strengths = []
    for count, rate in ((n_low, low), (n_high, high)):
        probability = rate / n_bits
        for _ in range(count):
            child, _average = mate(pop, scores, sections, rng, share)
            nxt.append(mutate(child, rng, probability))
            strengths.append(rate)
    return nxt, carried, strengths


def inchworm_boosted_flips(generations_at_best: int, base_flips: float) -> float:
    """Expected flips for the weakest children while the best score is unchanged.

    The first 4 generations at a score use the base rate. On the 5th, the
    weakest children move to base + 4. Every 3 generations after that adds
    another 4, and the rate stops at 40.
    """
    if generations_at_best < INCHWORM_STUCK_GENERATIONS:
        return base_flips
    steps = 1 + (generations_at_best - INCHWORM_STUCK_GENERATIONS) // INCHWORM_BOOST_EVERY
    return min(INCHWORM_MAX_FLIPS, base_flips + INCHWORM_BOOST_FLIPS * steps)


def inchworm_next(pop, scores, sections, rng, base_probability, boosted_probability, share, elites):
    """Elites copied. Children are section crossovers.

    While the boosted rate is above the base rate, children are ordered by the
    average fitness of their parents. The lowest of those get the boosted rate.
    Everyone else, including the elites, stays at the base rate or is copied.
    """
    ranked = sorted(range(len(pop)), key=lambda i: scores[i], reverse=True)
    carried = {pop[i]: scores[i] for i in ranked[:elites]}
    nxt = [pop[i] for i in ranked[:elites]]
    drafted = [mate(pop, scores, sections, rng, share) for _ in range(len(pop) - elites)]
    boosting = boosted_probability > base_probability
    if boosting:
        drafted.sort(key=lambda item: item[1], reverse=True)
        n_boost = min(INCHWORM_BOOST_COUNT, len(drafted))
    else:
        n_boost = 0
    split = len(drafted) - n_boost
    for index, (child, _expected) in enumerate(drafted):
        probability = boosted_probability if index >= split else base_probability
        nxt.append(mutate(child, rng, probability))
    return nxt, carried


def bandit_next(pop, scores, sections, rng, share, elites, n_flips, bandit, score, physical_evals, child_rates=None):
    """Elites copied. Every other slot is one section-crossover child, then an exact flip.

    `bandit` is None for uniform flips across the genome. With a bandit, each
    child is scored before and after the flip, and those two fitnesses update
    the flipped sections before the next child is drawn. `score` is the board
    fitness. `physical_evals` returns the cumulative board-evaluation count.
    The returned logs are the UCB children, in population order after the elites.
    `child_rates` gives each child its own expected flip count. A count of zero
    leaves that child unflipped and does not update the bandit.
    """
    ranked = sorted(range(len(pop)), key=lambda i: scores[i], reverse=True)
    carried = {pop[i]: scores[i] for i in ranked[:elites]}
    nxt = [pop[i] for i in ranked[:elites]]
    rates = list(child_rates) if child_rates is not None else [n_flips] * (len(pop) - elites)
    logs = []
    for rate in rates:
        crossover_child, _average = mate(pop, scores, sections, rng, share)
        if bandit is None:
            count = rate if isinstance(rate, int) else realized_flips(rng, rate)
            genes = () if count == 0 else tuple(rng.sample(range(len(crossover_child)), count))
            nxt.append(flip_exact(crossover_child, genes))
            continue
        baseline = score(crossover_child)
        record = bandit.propose(rng, rate)
        mutated = flip_exact(crossover_child, record.genes)
        mutated_fitness = score(mutated)
        if record.genes:
            reward, changed = impact_reward(baseline, mutated_fitness)
            bandit.observe(record.sections_flipped, reward)
        else:
            reward, changed = None, False
        logs.append({
            "crossover_fitness": baseline,
            "mutated_fitness": mutated_fitness,
            "behavior_changed": changed,
            "reward": reward,
            "expected_flips": rate,
            "sections_selected": list(record.sections_selected),
            "sections_flipped": list(record.sections_flipped),
            "genes_flipped_per_section": dict(record.genes_flipped_per_section),
            "physical_evals": physical_evals(),
        })
        nxt.append(mutated)
    return nxt, carried, logs


def hill_keep(current: float, challenger: float, accept: str) -> bool:
    """neutral keeps a tie. improve keeps only a strict gain."""
    if accept == "improve":
        return challenger > current
    return challenger >= current
