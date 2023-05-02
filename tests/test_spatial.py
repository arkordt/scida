from tests.testdata_properties import require_testdata


@require_testdata("areposnapshot_withcatalog")
def test_coordsalias(testdata_areposnapshot_withcatalog):
    obj = testdata_areposnapshot_withcatalog  # load(testdatapath)
    assert obj.file is not None
    assert obj.data is not None
    for ptype in ["PartType%i" % i for i in range(6)] + ["Group", "Subhalo"]:
        if ptype not in obj.data or ptype == "PartType3":
            continue
        coords = obj.get_coords(parttype=ptype)
        assert coords is not None