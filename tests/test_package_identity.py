def test_mstar_package_exports_public_api():
    import mstar

    assert mstar.__name__ == "mstar"
    assert callable(mstar.load_dataset)
    assert callable(mstar.configure_cache)
