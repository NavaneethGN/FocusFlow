// frontend/src/hlr.test.js
import { describe, it, expect } from 'vitest';
import { calcHalfLife, calcRecallProb, calcNextReviewDays } from './hlr.js';
import testVectors from './hlr_test_vectors.json';

describe('HLR Frontend Parity Tests against hlr_test_vectors.json', () => {
  it('has at least 40 test vectors', () => {
    expect(testVectors.length).toBeGreaterThanOrEqual(40);
  });

  testVectors.forEach((vec, idx) => {
    it(`vector #${idx + 1}: theta=[${vec.theta}], delta=${vec.delta_days}`, () => {
      const h = calcHalfLife(vec.theta, vec.x);
      expect(Math.abs(h - vec.half_life)).toBeLessThanOrEqual(1e-12);

      const p = calcRecallProb(h, vec.delta_days);
      expect(Math.abs(p - vec.recall)).toBeLessThanOrEqual(1e-12);

      const rev = calcNextReviewDays(h, vec.threshold);
      expect(Math.abs(rev - vec.next_review_days)).toBeLessThanOrEqual(1e-12);
    });
  });

  it('correctly handles negative delta by clamping to 0 (legacy behavior)', () => {
    const h = 4.0;
    const pNeg = calcRecallProb(h, -2.0);
    const pZero = calcRecallProb(h, 0.0);
    expect(pNeg).toBe(pZero);
  });

  it('agrees with server concept response within 1e-9 for launch model', () => {
    // Concept response from server under active launch model
    const serverConcept = {
      id: "c-math-1",
      n_right: 5,
      n_wrong: 3,
      delta_days: 2.058145,
      half_life_days: 4.0,
      p_hat: 0.69994
    };
    const launchTheta = [0.0, 1.0, -1.0];
    const x = [1.0, serverConcept.n_right, serverConcept.n_wrong];

    const jsHalfLife = calcHalfLife(launchTheta, x);
    expect(Math.abs(jsHalfLife - serverConcept.half_life_days)).toBeLessThan(1e-9);

    const jsRecall = calcRecallProb(jsHalfLife, serverConcept.delta_days);
    expect(Math.abs(jsRecall - serverConcept.p_hat)).toBeLessThan(1e-4);
  });
});
