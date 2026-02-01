"""
Rydberg Hamiltonian Learning Simulation
========================================
Simulates the hierarchical Hamiltonian learning protocol from Hu et al. (2025)
on a 5-atom static Rydberg chain (Example 2 / Appendix H of the paper).

Usage:
    python Ryd_sim.py          # prints results + saves figures
"""

import numpy as np
from scipy.linalg import expm
import matplotlib.pyplot as plt
from itertools import product

# ── Physical parameters ──────────────────────────────────────────────
N = 5                          # number of atoms
d = 10.0                       # inter-atom spacing (μm)
C6 = 862690.0                  # C6 coefficient (2π MHz μm⁶) for 70S_{1/2}
OMEGA = 1.5                    # Rabi frequency (2π MHz)
DELTA = -4.0                   # detuning (2π MHz), red-detuned

# ── Pauli matrices ───────────────────────────────────────────────────
I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
PAULIS = {"I": I2, "X": X, "Y": Y, "Z": Z}

DIM = 2**N


def kron_list(mats):
    """Tensor product of a list of matrices."""
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def pauli_label(indices):
    """Convert tuple of 0-3 to Pauli string label."""
    letters = "IXYZ"
    return "".join(letters[i] for i in indices)


def pauli_matrix(label):
    """Build N-qubit Pauli matrix from string like 'XIIIZ'."""
    mats = [PAULIS[c] for c in label]
    return kron_list(mats)


# ── Build Rydberg Hamiltonian ────────────────────────────────────────
def build_hamiltonian():
    """
    H = (Ω/2) Σ_l X_l  -  Δ Σ_l n_l  +  Σ_{j<l} V_{jl} n_j n_l
    where n_l = |r><r| = (I - Z_l)/2  and X_l is the Pauli X on site l.
    """
    H = np.zeros((DIM, DIM), dtype=complex)

    for l in range(N):
        # Rabi: (Ω/2) X_l
        ops = [I2] * N
        ops[l] = X
        H += (OMEGA / 2) * kron_list(ops)

    for l in range(N):
        # Detuning: -Δ n_l = -Δ (I - Z_l)/2
        ops_I = [I2] * N
        ops_Z = [I2] * N
        ops_Z[l] = Z
        H += -DELTA * 0.5 * (kron_list(ops_I) - kron_list(ops_Z))

    for j in range(N):
        for l in range(j + 1, N):
            dist = abs(l - j) * d
            Vjl = C6 / dist**6
            # V_{jl} n_j n_l = V_{jl} (I-Z_j)/2 (I-Z_l)/2
            # = V_{jl}/4 (II - IZ_l - Z_jI + Z_jZ_l)
            ops_II = [I2] * N
            ops_Zl = [I2] * N; ops_Zl[l] = Z
            ops_Zj = [I2] * N; ops_Zj[j] = Z
            ops_ZZ = [I2] * N; ops_ZZ[j] = Z; ops_ZZ[l] = Z
            H += Vjl / 4 * (kron_list(ops_II) - kron_list(ops_Zl)
                            - kron_list(ops_Zj) + kron_list(ops_ZZ))
    return H


# ── Exact Pauli decomposition ───────────────────────────────────────
def pauli_decompose(H):
    """Decompose H = Σ μ_s P_s.  Returns dict {label: coeff}."""
    coeffs = {}
    for indices in product(range(4), repeat=N):
        label = pauli_label(indices)
        P = pauli_matrix(label)
        mu = np.real(np.trace(H @ P)) / DIM
        if abs(mu) > 1e-14:
            coeffs[label] = mu
    return coeffs


# ── Bell-basis sampling (structure learning, A^I) ───────────────────
def bell_sampling(H_residual, tau, n_shots):
    """
    Simulate Bell sampling to discover Pauli support of H_residual.

    For small tau, P(s) ≈ τ² μ_s² for non-identity Paulis.
    We use exact probabilities from the Pauli decomposition rather than
    full 2n-qubit simulation (equivalent in expectation).
    """
    coeffs = pauli_decompose(H_residual)
    # Probability of sampling each Pauli ∝ sin²(μ_s τ) ≈ (μ_s τ)² for small τ
    labels = []
    probs = []
    for label, mu in coeffs.items():
        if label == "I" * N:
            continue
        p = np.sin(mu * tau) ** 2
        labels.append(label)
        probs.append(p)
    probs = np.array(probs)
    if probs.sum() < 1e-30:
        return {}
    probs /= probs.sum()

    counts = np.random.multinomial(n_shots, probs)
    discovered = {}
    for label, count in zip(labels, counts):
        if count > 0:
            discovered[label] = count
    return discovered


# ── Coefficient estimation (A^II) ───────────────────────────────────
def estimate_coefficient_direct(H_residual, pauli_label_s, n_shots, eps):
    """
    Estimate μ_s = Tr[P_s H_res] / 2^N with simulated shot noise.

    The real protocol uses robust frequency estimation with evolution
    time T ∝ 1/ε, achieving precision ε with O(log(1/ε)) overhead.
    Here we simulate this: the estimator achieves std ~ ε with the
    given shot budget at this level.
    """
    coeffs = pauli_decompose(H_residual)
    mu_true = coeffs.get(pauli_label_s, 0.0)
    # The protocol achieves precision ε per coefficient at each level
    noise_std = eps / np.sqrt(n_shots / 100)  # ~ε for 100 effective shots
    mu_est = mu_true + np.random.normal(0, noise_std)
    return mu_est


# ── Hierarchical learning ───────────────────────────────────────────
# Parameters from Appendix H
LEVELS = [
    {"T": 0.08,   "eps": 5e-3},
    {"T": 0.2,    "eps": 5e-3},
    {"T": 6.0,    "eps": 1e-3},
    {"T": 60.0,   "eps": 1e-4},
    {"T": 1200.0, "eps": 1e-5},
]
STRUCTURE_SHOTS = 2000
COEFF_SHOTS = 1000


def run_hierarchical_learning(H_true, true_coeffs, verbose=True):
    """Run J=5 levels of hierarchical Hamiltonian learning."""
    # Start with identity coefficient (global phase, not learnable)
    id_label = "I" * N
    id_coeff = true_coeffs.get(id_label, 0.0)
    H_hat = id_coeff * np.eye(DIM, dtype=complex)
    hat_coeffs = {id_label: id_coeff}
    results = []

    for j, level in enumerate(LEVELS):
        T = level["T"]
        eps = level["eps"]
        if verbose:
            print(f"\n{'='*60}")
            print(f"Level {j+1}: T = {T} μs, ε = {eps}")
            print(f"{'='*60}")

        # Residual Hamiltonian
        H_res = H_true - H_hat

        # Trotter number for this level
        r1 = max(1, int(np.ceil(T * sum(abs(v) for v in true_coeffs.values()) / 0.1)))
        tau = T / r1

        # ── Structure learning (A^I) ──
        discovered = bell_sampling(H_res, tau, STRUCTURE_SHOTS)
        if verbose:
            print(f"  Structure learning: discovered {len(discovered)} Pauli terms")

        # ── Coefficient learning (A^II) ──
        level_coeffs = {}
        for label in discovered:
            mu_est = estimate_coefficient_direct(H_res, label, COEFF_SHOTS, eps)
            level_coeffs[label] = mu_est

        # Update classical description
        for label, mu in level_coeffs.items():
            hat_coeffs[label] = hat_coeffs.get(label, 0.0) + mu

        # Rebuild H_hat from coefficients
        H_hat = np.zeros((DIM, DIM), dtype=complex)
        for label, mu in hat_coeffs.items():
            H_hat += mu * pauli_matrix(label)

        # Evaluate error
        residual_norm = np.linalg.norm(H_true - H_hat, ord=2)
        if verbose:
            print(f"  Residual ‖H - Ĥ‖ = {residual_norm:.6f} (2π MHz)")
            print(f"  Learned {len(hat_coeffs)} total Pauli terms so far")

        results.append({
            "level": j + 1,
            "T": T,
            "eps": eps,
            "n_terms": len(hat_coeffs),
            "residual": residual_norm,
            "hat_coeffs": dict(hat_coeffs),
        })

    return results, hat_coeffs


# ── Plotting ─────────────────────────────────────────────────────────
def plot_results(true_coeffs, hat_coeffs, save_prefix="theory/Posts/Ham_learning/"):
    """Generate bar chart comparison and 1/r⁶ decay plot."""

    # ── Bar chart: learned vs true coefficients ──
    # Sort by magnitude of true coefficient
    all_labels = sorted(
        set(list(true_coeffs.keys()) + list(hat_coeffs.keys())),
        key=lambda s: -abs(true_coeffs.get(s, 0.0))
    )
    # Filter to non-trivial terms (drop pure identity)
    all_labels = [l for l in all_labels if l != "I" * N]
    # Keep top terms for readability
    all_labels = all_labels[:25]

    true_vals = [true_coeffs.get(l, 0.0) for l in all_labels]
    hat_vals = [hat_coeffs.get(l, 0.0) for l in all_labels]

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(all_labels))
    w = 0.35
    ax.bar(x - w/2, true_vals, w, label="True $\\mu_s$", color="steelblue")
    ax.bar(x + w/2, hat_vals, w, label="Learned $\\hat{\\mu}_s$", color="coral")
    ax.set_xticks(x)
    ax.set_xticklabels(all_labels, rotation=90, fontsize=7)
    ax.set_ylabel("Coefficient (2π MHz)")
    ax.set_title("Pauli coefficients: true vs learned (5-atom Rydberg chain)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_prefix + "coefficients.png", dpi=150)
    plt.close(fig)
    print(f"Saved {save_prefix}coefficients.png")

    # ── 1/r⁶ decay of ZZ interactions ──
    zz_true = {}
    zz_learned = {}
    for j in range(N):
        for l in range(j + 1, N):
            label = ["I"] * N
            label[j] = "Z"
            label[l] = "Z"
            label = "".join(label)
            dist = abs(l - j) * d
            zz_true[dist] = true_coeffs.get(label, 0.0)
            zz_learned[dist] = hat_coeffs.get(label, 0.0)

    dists = sorted(zz_true.keys())
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    ax2.loglog(dists, [abs(zz_true[dd]) for dd in dists], "o-",
               label="True $V_{jl}/4$", color="steelblue")
    ax2.loglog(dists, [max(abs(zz_learned.get(dd, 0)), 1e-15) for dd in dists],
               "s--", label="Learned", color="coral")
    # Reference 1/r⁶ line
    d_ref = np.array(dists)
    scale = abs(zz_true[dists[0]]) * dists[0]**6
    ax2.loglog(d_ref, scale / d_ref**6, ":", color="gray", label="$1/r^6$")
    ax2.set_xlabel("Distance (μm)")
    ax2.set_ylabel("|ZZ coefficient| (2π MHz)")
    ax2.set_title("Van der Waals $1/r^6$ decay")
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(save_prefix + "vdw_decay.png", dpi=150)
    plt.close(fig2)
    print(f"Saved {save_prefix}vdw_decay.png")


# ── Main ─────────────────────────────────────────────────────────────
def main():
    np.random.seed(42)

    print("Building 5-atom Rydberg Hamiltonian …")
    H = build_hamiltonian()
    true_coeffs = pauli_decompose(H)
    print(f"True Hamiltonian has {len(true_coeffs)} non-zero Pauli terms")

    # Print largest terms
    sorted_terms = sorted(true_coeffs.items(), key=lambda x: -abs(x[1]))
    print("\nTop 15 Pauli terms:")
    print(f"  {'Label':<8s}  {'μ (2π MHz)':>12s}")
    print(f"  {'─'*8}  {'─'*12}")
    for label, mu in sorted_terms[:15]:
        print(f"  {label:<8s}  {mu:>12.6f}")

    print("\n\nRunning hierarchical learning …")
    results, hat_coeffs = run_hierarchical_learning(H, true_coeffs)

    # Summary table
    print(f"\n\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  {'Level':>5}  {'T (μs)':>10}  {'ε':>10}  {'# terms':>8}  {'‖H-Ĥ‖':>12}")
    print(f"  {'─'*5}  {'─'*10}  {'─'*10}  {'─'*8}  {'─'*12}")
    for r in results:
        print(f"  {r['level']:>5}  {r['T']:>10.2f}  {r['eps']:>10.5f}"
              f"  {r['n_terms']:>8}  {r['residual']:>12.6f}")

    plot_results(true_coeffs, hat_coeffs)
    print("\nDone.")


if __name__ == "__main__":
    main()
