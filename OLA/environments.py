import numpy as np
from typing import Callable,Union

import optimization_utilities as opt

"""
Here I define the environments 
and the objects that keep track of the history and compute statistics
"""


class SingleClassEnvironment:

    def __init__(self,
                 N: Callable[[Union[float, np.ndarray]], Union[int, np.ndarray]], en: Callable[[], int],
                 C: Callable[[Union[float, np.ndarray]], Union[float, np.ndarray]], ec: Callable[[], float],
                 A: Callable[[Union[float, np.ndarray]], Union[float, np.ndarray]],
                 rng: np.random.Generator):
        """

        :param N: number of clicks given bid(s)
        :param en: noise for the number of clicks
        :param C: advertising cost given bids(s)
        :param ec: noise for the advertising costs
        :param A: conversion rate given price(s)
        :param rng: a numpy random generator (used for the Bernoulli for the conversions)
        """
        self.N = N
        self.en = en
        self.C = C
        self.ec = ec
        self.A = A
        self.rng = rng

    def perform_day(self, x: float, p: float):
        """
        :param x: the bid selected for the day
        :param p: the price selected for the day
        :return: (n,q,c)
        n: int - the number of clicks
        q: int - the number of conversions
        c: float - the advertising costs
        """
        n = int(self.N(x) + self.en())
        # potentially there is a small probability that the noise sets the number of clicks to less than 1 (or even
        # less than 0)
        if n < 1:
            n = 1
        samples = self.rng.binomial(n=1, p=self.A(p), size=n)
        q = np.sum(samples)
        c = self.C(x) + self.ec()
        if c < 0.1:
            c = 0.1
        return n, q, c


class SingleClassEnvironmentNonStationary:

    def __init__(self, N, en, C, ec, A, rng):
        """
        Parameters
        ----------
        N :
            N:bid->E[number of clicks]
        en : callable
            en() returns a sample from a gaussian distribution
        C : callable
            C:bid->E[payment for clicks]
        ec : callable
            ec() returns a sample from a gaussian distribution
        A : callable
            A(price, day) returns the conversion rate considering the day, and thus the phase
        rng : random generator
            a numpy random generator to be used (mostly for Bernoulli)

        Returns
        -------
        None.

        """
        self.N = N
        self.en = en
        self.C = C
        self.ec = ec
        self.A = A
        self.rng = rng

    def perform_day(self, x: float, p: float, day: int):
        """
        :param x: the bid selected for the day
        :param p: the price selected for the day
        :param day: the current day
        :return: (n,q,c)
        n: int - the number of clicks
        q: int - the number of conversions
        c: float - the advertising costs
        """
        n = int(self.N(x) + self.en())
        # potentially there is a small probability that the noise sets the number of clicks to less than 1 (or even
        # less than 0)
        if n < 1:
            n = 1
        samples = self.rng.binomial(n=1, p=self.A(p, day), size=n)
        q = np.sum(samples)
        c = self.C(x) + self.ec()
        if c < 0.1:
            c = 0.1
        return n, q, c


class SingleClassEnvironmentHistory:
    """
    History of all the steps performed by an environment
    Observe that it is not stored inside the environment itself, but by the learner
    """

    def __init__(self, env: SingleClassEnvironment):
        """
        :param env: ...
        """
        self.N = env.N
        self.C = env.C
        self.A = env.A

        self.xs = []
        self.ps = []
        self.ns = []
        self.qs = []
        self.cs = []

    def add_step(self, x: float, p: float, n: int, q: int, c: float):
        """
        Memorizes a new step (i.e., day) that has been performed

        Parameters
        ----------
        x : float
            the chosen bid
        p : float
            the chosen price
        n : int
            the number of clicks achieved
        q : int
            the number of conversions achieved
        c : float
            the advertising costs incurred in

        Returns
        -------
        None.

        """
        self.xs.append(x)
        self.ps.append(p)
        self.ns.append(n)
        self.qs.append(q)
        self.cs.append(c)

    def reward_stats(self, bids: np.ndarray, prices: np.ndarray):
        """
        Computes some things regarding the reward/regret during the history
        :param bids: the available bids
        :param prices: the available prices
        :return:
        instantaneous_rewards : numpy array
            the instantaneous rewards
        instantaneous_regrets : numpy array
            the instantaneous regrets
        cumulative_rewards : numpy array
            the cumulative rewards
        cumulative_regrets : numpy array
            the cumulative regrets
        """
        x_best, _, p_best, _ = opt.single_class_opt(bids, prices, self.A(prices), self.N(bids), self.C(bids))
        ps = np.array(self.ps)
        xs = np.array(self.xs)
        return self.compute_reward_stats(xs, ps, self.A, self.N, self.C, x_best, p_best)

    @staticmethod
    def compute_reward_stats(xs: np.ndarray, ps: np.ndarray,
                             A: callable, N: callable, C: callable,
                             best_bid: float, best_price: float):
        """
        :return:
        instantaneous_rewards : np.ndarray
            the instantaneous rewards for each time step
        instantaneous_regrets : np.ndarray
            the instantaneous regrets for each time step
        cumulative_rewards : np.ndarray
            the cumulative rewards for each time step
        cumulative_regrets : np.ndarray
            the cumulative regrets for each time step
        """
        alphas = A(ps)

        # here maybe I should use the actual number of conversions and advertising costs with the noise?
        instantaneous_rewards = alphas * ps * N(xs) - C(xs)

        best_reward = A(best_price) * best_price * N(best_bid) - C(best_bid)

        instantaneous_regrets = best_reward - instantaneous_rewards

        return instantaneous_rewards, instantaneous_regrets, np.cumsum(instantaneous_rewards), np.cumsum(
            instantaneous_regrets)

    def played_rounds(self):
        return len(self.ps)


class SingleClassEnvironmentNonStationaryHistory:

    def __init__(self, env: SingleClassEnvironmentNonStationary):
        self.env = env
        self.xs = []
        self.ps = []
        self.ns = []
        self.qs = []
        self.cs = []

    def add_step(self, x: float, p: float, n: int, q: int, c: float):
        """
        Memorizes a new step (i.e., day)
        :param x: the chosen bid
        :param p: the chosen price
        :param n: the achieved number of clicks
        :param q: the achieved number of conversions
        :param c: the achieved advertising cost
        :return: None
        """
        self.xs.append(x)
        self.ps.append(p)
        self.ns.append(n)
        self.qs.append(q)
        self.cs.append(c)

    def reward_stats(self, bids: np.ndarray, prices: np.ndarray):
        """

        :param bids:
        :param prices:
        :return: (instantaneous rewards, instantaneous regrets, cumulative rewards, cumulative regrets)
        """
        ps = np.array(self.ps)
        xs = np.array(self.xs)
        rs = np.zeros(ps.shape[0])
        best_rs = np.zeros(ps.shape[0])
        # compute the optimal reward at each time step
        for t in ps.shape[0]:
            alphas = np.array([self.env.A(p, t) for p in prices])
            x_best, _, p_best, _ = opt.single_class_opt(bids, prices, alphas, self.env.N(bids), self.env.C(bids))

            best_rs[t] = self.env.A(p_best,t) * p_best * self.env.N(x_best) - self.env.C(x_best)
            rs = self.env.A(ps[t], t) * ps[t] * self.env.N(xs[t]) - self.env.C(xs[t])

        instantaneous_regrets = best_rs - rs

        return rs, instantaneous_regrets, np.cumsum(rs), np.cumsum(
            instantaneous_regrets)


class MultiClassEnvironment:
    """
    The complete multi-class environment
    (works also when the estimated classes are not the true ones)
    """

    def __init__(self, n_features: int, class_map: dict, user_prob_map: dict,
                 n: list, en: Callable, c: list, ec: Callable, a: list, rng: np.random.Generator):
        """
        :param n_features: the number of features
        :param class_map: a mapping user_type->class (tuple->int), classes are from 0 to len(n)=len(c)=len(a)
        :param user_prob_map: a mapping user_type->probability
        :param n: a list of functions for the number of clicks
        :param en: the noise for the number of clicks
        :param c: a list of functions for the advertising costs
        :param ec: the noise for the advertising costs
        :param a: a list of functions for the conversion rates
        :param rng: a numpy random number generator that will be used by this object
        """
        self.n_features = n_features
        self.class_map = class_map
        self.user_prob_map = user_prob_map
        self.n = n
        self.en = en
        self.c = c
        self.ec = ec
        self.a = a
        self.rng = rng
        self.user_profiles = class_map.keys()

    def perform_day(self, bids: dict, prices: dict):
        """
        :param bids: a mapping user_profile->bid
        :param prices: a mapping user_profile->price
        :return: a mapping user_profile->(n,q,c)
        n: int - the number of clicks for that user profile
        q: int - the number of conversions for that user profile
        c: float - the advertising costs for that user profile
        """
        result = {}
        for user_prof in self.user_profiles:
            bid = bids[user_prof]
            price = prices[user_prof]
            user_class = self.class_map[user_prof]
            user_prob = self.user_prob_map[user_prof]
            n = (self.n[user_class](bid) + self.en()) * user_prob
            n = int(n)
            # there is the possibility that the noise reduces n below 1
            if n < 1:
                n = 1
            # I am pretty sure that Binomial exists in the standard generator that we use
            samples = self.rng.binomial(n=1, p=self.a[user_class](price), size=n)
            q = np.sum(samples)
            c = (self.c[user_class](bid) + self.ec()) * user_prob
            # again due to the noise, we want to avoid negative values
            if c < 0.1:
                c = 0.1
            result[user_prof] = (n, q, c)
        return result

    def classes_count(self):
        return len(self.n)


class MultiClassEnvironmentHistory:
    def __init__(self, environment: MultiClassEnvironment):
        """
        :param environment: the multi class environment of which the history will be recorded
        """
        self.env = environment
        # for each user profile, the bid for each turn
        self.xs = {}
        # for each user profile, the price for each turn
        self.ps = {}
        # for each user profile, the number of clicks for each turn
        self.ns = {}
        # for each user profile, the number of conversions for each turn
        self.qs = {}
        # for each user profile, the advertising costs for each turn
        self.cs = {}
        # the number of turns played so far
        self.t = 0
        for user_profile in environment.user_profiles:
            self.xs[user_profile] = []
            self.ps[user_profile] = []
            self.ns[user_profile] = []
            self.qs[user_profile] = []
            self.cs[user_profile] = []

    def add_step(self, x: dict, p: dict, step_results: dict):
        """
        Memorizes a new step (i.e., day) that has been performed
        :param x: mapping user_profile->bid
        :param p: mapping user_profile->price
        :param step_results: mapping user_profile-> (n,q,c) as in MultiClassEnvironment.perform_day
        :return:
        """
        for user_profile in self.env.user_profiles:
            self.xs[user_profile].append(x[user_profile])
            self.ps[user_profile].append(p[user_profile])
            n, q, c = step_results[user_profile]
            self.ns[user_profile].append(n)
            self.qs[user_profile].append(q)
            self.cs[user_profile].append(c)
        self.t += 1

    def played_rounds(self):
        return self.t

    def stats_for_user_profile(self, bids: np.ndarray, prices: np.ndarray):
        """
        :param bids: the available bids
        :param prices: the available prices
        :return: (instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets)
        dictionaries, each one contains, for each user profile, an array with the data for each time step
        """
        instantaneous_rewards = {}
        instantaneous_regrets = {}
        cumulative_rewards = {}
        cumulative_regrets = {}

        alphas = np.array([self.env.a[c](prices) for c in range(self.env.classes_count())])
        ns = np.array([self.env.n[c](bids) for c in range(self.env.classes_count())])
        cs = np.array([self.env.c[c](bids) for c in range(self.env.classes_count())])
        best_bids, _, best_prices, _ = opt.multi_class_opt(bids, prices, alphas, ns, cs)

        for user_profile in self.env.user_profiles:
            class_index = self.env.class_map[user_profile]
            res_tuple = SingleClassEnvironmentHistory.compute_reward_stats(np.array(self.xs[user_profile]),
                                                                           np.array(self.xs[user_profile]),
                                                                           self.env.a[class_index],
                                                                           self.env.n[class_index],
                                                                           self.env.c[class_index],
                                                                           best_bids[class_index],
                                                                           best_prices[class_index])
            rewards, regrets, cum_rewards, cum_regrets = res_tuple
            instantaneous_rewards[user_profile] = rewards
            instantaneous_regrets[user_profile] = regrets
            cumulative_rewards[user_profile] = cumulative_rewards
            cumulative_regrets[user_profile] = cumulative_regrets
        return instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets

    def stats_for_class(self, bids: np.ndarray, prices: np.ndarray):
        """

        :param bids: the available bids
        :param prices: the available prices
        :return: instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets
        They are all matrices of shape (n_classes, T)
        matrix[c,t] = value at time t for class c
        """
        # basically instantaneous_rewards[c,t]= reward at time t from users of class c
        instantaneous_rewards = np.zeros(shape=(max(self.env.class_map.values()), self.played_rounds()))
        instantaneous_regrets = np.zeros(shape=(max(self.env.class_map.values()), self.played_rounds()))
        cumulative_rewards = np.zeros(shape=(max(self.env.class_map.values()), self.played_rounds()))
        cumulative_regrets = np.zeros(shape=(max(self.env.class_map.values()), self.played_rounds()))

        # data for single user profiles
        rewards, regrets, cum_rewards, cum_regrets = self.stats_for_user_profile(bids, prices)

        # put things together according to the class
        for user_profile in self.env.user_profiles:
            c = self.env.class_map[user_profile]
            instantaneous_rewards[c, :] = instantaneous_rewards[c, :] + rewards[user_profile]
            instantaneous_regrets[c, :] = instantaneous_regrets[c, :] + regrets[user_profile]
            cumulative_rewards[c, :] = cumulative_rewards[c, :] + cum_rewards[user_profile]
            cumulative_regrets[c, :] = cumulative_regrets[c, :] + cum_regrets[user_profile]
        return instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets

    def stats_total(self, bids: np.ndarray, prices: np.ndarray):
        """

        :param bids: the available bids
        :param prices: the available prices
        :return: instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets
        for each time step, the total (i.e. considering all the classes) values
        """
        instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets = self.stats_for_class(bids, prices)
        instantaneous_rewards = np.sum(instantaneous_rewards, axis=0)
        instantaneous_regrets = np.sum(instantaneous_regrets, axis=0)
        cumulative_rewards = np.sum(cumulative_rewards, axis=0)
        cumulative_regrets = np.sum(cumulative_regrets, axis=0)
        return instantaneous_rewards, instantaneous_regrets, cumulative_rewards, cumulative_regrets

    def get_raw_data(self):
        # TODO: we should create a class that only contains the historic data and that is wrapped by the history classes
        # actually the class must go to the context generation class with its own constructor
        # instead of this method
        # observe that instead of dividing the dataset we memorize which user profiles to consider in the split
        return {
            "profiles": set(self.env.user_profiles),
            "bids": self.xs,
            "prices": self.ps,
            "clicks": self.ns,
            "conversions": self.qs,
            "costs": self.cs
        }
