from services.blockchain.certificate_figures import (
    generate_2d_interaction_diagram,
    generate_energy_profile_plot,
    generate_gnn_attention_image,
    generate_shap_image,
    get_2d_image,
)


def test_certificate_figure_renderers_return_reportlab_images_for_valid_data():
    assert get_2d_image("CCO") is not None
    assert generate_energy_profile_plot([{"rank": 1, "affinity": -7.1}]) is not None
    assert generate_shap_image({"logp": 0.3, "tpsa": -0.1}) is not None
    assert generate_gnn_attention_image("CCO", [0.2, 0.5, 0.3]) is not None
    assert generate_2d_interaction_diagram(
        "CCO", [{"residue": "ASP186 A", "distance": "2.8 Å", "type": "H-Bond"}]
    ) is not None


def test_certificate_figure_renderers_keep_empty_and_invalid_input_fallbacks():
    assert get_2d_image("not-smiles") is None
    assert generate_energy_profile_plot([]) is None
    assert generate_shap_image({}) is None
    assert generate_gnn_attention_image("CCO", []) is None
    assert generate_2d_interaction_diagram("not-smiles", []) is None
