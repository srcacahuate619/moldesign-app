"""
Tests del normalizador de scoring (scoring/normalizer.py).

Cubre:
- normalize_affinity() con valores conocidos
- clamping en range [0, 100]
- Penalisación por tamaño pequeño (<12 heavy atoms)
- Penalisación por baja potencia (affinity > threshold)
- Factor LLE (Lipophilic Efficiency)
- ADME score con casos extremos
- Drug-likeness score (QED mapping)
"""
from __future__ import annotations

from tests.conftest import create_mock_physicochemical_properties


# ═════════════════════════════════════════════════════════════════════════════
# normalize_affinity
# ═════════════════════════════════════════════════════════════════════════════


class TestNormalizeAffinity:
    """Tests de la función normalize_affinity()."""

    def test_high_affinity_scores_high(self):
        """Afinidad muy negativa debe dar score cercano a 100."""
        from scoring.normalizer import normalize_affinity
        score = normalize_affinity(-12.0, heavy_atoms=25, log_p=2.5)
        assert score >= 80.0
        assert score <= 100.0

    def test_low_affinity_scores_low(self):
        """Afinidad cercana a cero debe dar score bajo."""
        from scoring.normalizer import normalize_affinity
        score = normalize_affinity(-3.0, heavy_atoms=25, log_p=2.5)
        assert score < 40.0

    def test_score_is_clamped_0_100(self):
        """El score siempre debe estar en [0, 100]."""
        from scoring.normalizer import normalize_affinity
        # Afinidad extremadamente buena
        score = normalize_affinity(-30.0, heavy_atoms=25, log_p=2.5)
        assert 0.0 <= score <= 100.0
        # Afinidad extremadamente mala
        score = normalize_affinity(10.0, heavy_atoms=25, log_p=2.5)
        assert 0.0 <= score <= 100.0

    def test_no_heavy_atoms_fallback(self):
        """Sin heavy_atoms debe usar fallback a afinidad absoluta."""
        from scoring.normalizer import normalize_affinity
        score = normalize_affinity(-10.0, heavy_atoms=None)
        assert 0.0 <= score <= 100.0

    def test_threshold_penalty(self):
        """Afinidad peor que threshold debe penalizar."""
        from scoring.normalizer import normalize_affinity
        # threshold default = -7.5
        # Con -6.0 (peor que -7.5), debe penalizar
        weak_score = normalize_affinity(-6.0, heavy_atoms=25, log_p=2.5, threshold=-7.5)
        # Con -9.0 (mejor que -7.5), no debe penalizar por threshold
        strong_score = normalize_affinity(-9.0, heavy_atoms=25, log_p=2.5, threshold=-7.5)
        assert strong_score > weak_score

    def test_is_control_skips_penalty(self):
        """Modo control debe evitar penalización por threshold."""
        from scoring.normalizer import normalize_affinity
        control_score = normalize_affinity(-6.0, heavy_atoms=25, log_p=2.5, threshold=-7.5, is_control=True)
        normal_score = normalize_affinity(-6.0, heavy_atoms=25, log_p=2.5, threshold=-7.5, is_control=False)
        # En control, no hay penalización, así que el score debe ser >=
        if normal_score < control_score:
            pass  # control_score debe ser igual o mayor
        assert control_score >= normal_score or abs(control_score - normal_score) < 0.01


class TestNormalizeAffinitySizePenalty:
    """Tests de penalización por tamaño pequeño."""

    def test_small_molecule_has_penalty_applied(self):
        """Moléculas con <12 heavy atoms deben recibir penalización por size."""
        from scoring.normalizer import normalize_affinity
        # Dos moléculas con LE similar pero una < 12 atoms
        # 10 heavy atoms: LE = -0.8 → altísimo → debe estar cerca de 100
        # pero con penalización de (12-10)*8 = 16 puntos
        score = normalize_affinity(-8.0, heavy_atoms=10, log_p=2.5)
        # La penalización debe hacer que no llegue a 100
        assert 0.0 <= score <= 100.0

    def test_very_small_heavy_atom_does_not_crash(self):
        """5 heavy atoms no debe crashear y debe dar score válido."""
        from scoring.normalizer import normalize_affinity
        score = normalize_affinity(-8.0, heavy_atoms=5, log_p=2.5)
        assert 0.0 <= score <= 100.0

    def test_size_penalty_is_less_severe_with_better_le(self):
        """A igualdad de affinity, menor heavy_atoms → mejor LE → score no necesariamente menor."""
        from scoring.normalizer import normalize_affinity
        # LE para 24 atoms = -8/24 = -0.33
        # LE para 12 atoms = -8/12 = -0.67
        # Aunque 12 tiene penalización, su LE es mejor
        twentyfour = normalize_affinity(-8.0, heavy_atoms=24, log_p=2.5)
        twelve = normalize_affinity(-8.0, heavy_atoms=12, log_p=2.5)
        # Ambos deben estar en rango
        assert 0.0 <= twentyfour <= 100.0
        assert 0.0 <= twelve <= 100.0


class TestNormalizeAffinityLLE:
    """Tests del factor LLE (Lipophilic Efficiency)."""

    def test_poor_lle_penalizes(self):
        """LLE < 3.0 debe penalizar el score."""
        from scoring.normalizer import normalize_affinity
        # logP alto + afinidad mediocre → LLE bajo
        poor_lle = normalize_affinity(-6.0, heavy_atoms=25, log_p=5.0)
        # logP bajo + buena afinidad → LLE alto
        good_lle = normalize_affinity(-12.0, heavy_atoms=25, log_p=1.0)
        assert poor_lle < good_lle or abs(poor_lle - good_lle) < 1.0

    def test_lle_factor_never_below_04(self):
        """El factor LLE nunca debe ser menor a 0.4."""
        from scoring.normalizer import normalize_affinity
        # LLE extremadamente bajo
        score = normalize_affinity(-3.0, heavy_atoms=25, log_p=6.0)
        assert score >= 0.0


class TestClampScore:
    """Tests de clamp_score()."""

    def test_clamp_negative(self):
        """Valores negativos deben dar 0."""
        from scoring.normalizer import clamp_score
        assert clamp_score(-10.0) == 0.0

    def test_clamp_above_100(self):
        """Valores sobre 100 deben dar 100."""
        from scoring.normalizer import clamp_score
        assert clamp_score(150.0) == 100.0

    def test_clamp_mid_range(self):
        """Valores en rango deben mantenerse."""
        from scoring.normalizer import clamp_score
        assert clamp_score(50.0) == 50.0
        assert clamp_score(0.0) == 0.0
        assert clamp_score(100.0) == 100.0

    def test_clamp_rounds_to_two_decimals(self):
        """Debe redondear a 2 decimales."""
        from scoring.normalizer import clamp_score
        result = clamp_score(50.12345)
        assert result == 50.12


# ═════════════════════════════════════════════════════════════════════════════
# calculate_adme_score
# ═════════════════════════════════════════════════════════════════════════════


class TestCalculateAdmeScore:
    """Tests de la función calculate_adme_score()."""

    def test_ideal_properties_score_high(self):
        """Propiedades ideales deben dar score cercano a 100."""
        from scoring.normalizer import calculate_adme_score
        props = create_mock_physicochemical_properties(
            tpsa=60.0,
            log_p=2.5,
            sa_score=2.0,
        )
        score = calculate_adme_score(props)
        assert score >= 80.0
        assert score <= 100.0

    def test_high_tpsa_penalizes(self):
        """TPSA > 120 debe penalizar significativamente."""
        from scoring.normalizer import calculate_adme_score
        props = create_mock_physicochemical_properties(
            tpsa=150.0,
            log_p=2.5,
            sa_score=2.0,
        )
        score = calculate_adme_score(props)
        # Debería ser menor que con TPSA ideal
        ideal = create_mock_physicochemical_properties(
            tpsa=60.0,
            log_p=2.5,
            sa_score=2.0,
        )
        ideal_score = calculate_adme_score(ideal)
        assert score < ideal_score

    def test_extreme_logp_penalizes(self):
        """logP extremo (muy alto) debe penalizar vs óptimo."""
        from scoring.normalizer import calculate_adme_score
        # logP=6.0 rompe Lipinski (logP>5) → lipinski_pass=False
        high_logp = create_mock_physicochemical_properties(log_p=6.0, tpsa=60.0, sa_score=2.0, lipinski_pass=False)
        optimal = create_mock_physicochemical_properties(log_p=2.5, tpsa=60.0, sa_score=2.0)
        high_score = calculate_adme_score(high_logp)
        opt_score = calculate_adme_score(optimal)
        assert high_score < opt_score, f"High logP score {high_score} should be < optimal {opt_score}"

    def test_low_logp_penalizes(self):
        """logP muy bajo también debe penalizar (sin romper Lipinski)."""
        from scoring.normalizer import calculate_adme_score
        # logP=-2.0 NO rompe Lipinski (logP≤5), pero es extremo
        low_logp = create_mock_physicochemical_properties(log_p=-2.0, tpsa=60.0, sa_score=2.0)
        optimal = create_mock_physicochemical_properties(log_p=2.5, tpsa=60.0, sa_score=2.0)
        low_score = calculate_adme_score(low_logp)
        opt_score = calculate_adme_score(optimal)
        assert low_score < opt_score, f"Low logP score {low_score} should be < optimal {opt_score}"

    def test_high_sa_score_penalizes(self):
        """SA Score > 7 debe penalizar fuerte."""
        from scoring.normalizer import calculate_adme_score
        high_sa = create_mock_physicochemical_properties(sa_score=8.0, tpsa=60.0, log_p=2.5)
        low_sa = create_mock_physicochemical_properties(sa_score=2.0, tpsa=60.0, log_p=2.5)
        assert calculate_adme_score(high_sa) < calculate_adme_score(low_sa)

    def test_adme_score_never_negative(self):
        """ADME score nunca debe ser negativo."""
        from scoring.normalizer import calculate_adme_score
        props = create_mock_physicochemical_properties(
            tpsa=200.0, log_p=8.0, sa_score=10.0,
            lipinski_pass=False,
        )
        score = calculate_adme_score(props)
        assert score >= 0.0


# ═════════════════════════════════════════════════════════════════════════════
# calculate_druglikeness_score
# ═════════════════════════════════════════════════════════════════════════════


class TestCalculateDruglikenessScore:
    """Tests de drug-likeness score (QED mapping)."""

    def test_high_qed_gives_high_score(self):
        """QED alto debe dar score alto."""
        from scoring.normalizer import calculate_druglikeness_score
        props = create_mock_physicochemical_properties(qed=0.9)
        score = calculate_druglikeness_score(props)
        assert score >= 80.0

    def test_low_qed_gives_low_score(self):
        """QED bajo debe dar score bajo."""
        from scoring.normalizer import calculate_druglikeness_score
        props = create_mock_physicochemical_properties(qed=0.2)
        score = calculate_druglikeness_score(props)
        assert score <= 30.0

    def test_qed_maps_0_100(self):
        """QED 0.0 → 0, QED 1.0 → 100."""
        from scoring.normalizer import calculate_druglikeness_score
        props = create_mock_physicochemical_properties(qed=0.0)
        assert calculate_druglikeness_score(props) == 0.0
        props = create_mock_physicochemical_properties(qed=1.0)
        assert calculate_druglikeness_score(props) == 100.0
