// frontend/src/hlr.js
// HLR Math Helper (Duolingo: Settles & Meeder, 2016)

export const H_MIN = 15.0 / 1440.0;
export const H_MAX = 270.0;
export const P_MIN = 0.0001;
export const P_MAX = 0.9999;
export const DEFAULT_THRESHOLD = 0.70;
export const LAUNCH_THETA = [0.0, 1.0, -1.0];

export function calcHalfLife(theta, x) {
  const exponent = theta.reduce((acc, t, i) => acc + t * (x[i] || 0), 0);
  const h = Math.pow(2, exponent);
  return Math.min(Math.max(h, H_MIN), H_MAX);
}

export function calcRecallProb(h, deltaDays) {
  if (h <= 0) return P_MIN;
  const p = Math.pow(2, -Math.max(0, deltaDays) / h);
  return Math.min(Math.max(p, P_MIN), P_MAX);
}

export function calcNextReviewDays(h, threshold = DEFAULT_THRESHOLD) {
  if (threshold <= 0 || threshold >= 1) {
    threshold = DEFAULT_THRESHOLD;
  }
  return -h * Math.log2(threshold);
}
