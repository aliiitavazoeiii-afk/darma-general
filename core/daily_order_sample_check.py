# Reference expectations for the user's sample Digikala file
# packageDeliveryReport_1787646878386.xlsx. This file is not executed at runtime;
# it documents the validated aggregation used while implementing importer v8.
SAMPLE_EXPECTED = {
    ("تکوین", "2222", "L"): 2,
    ("تکوین", "4444", "XL"): 3,
    ("دارما", "400", "M"): 1,
    ("دارما", "400", "L"): 2,
    ("دارما", "400", "XL"): 1,
    ("دارما", "400", "XXL"): 1,
    ("دارما", "D 220", "M"): 1,
    ("دارما", "D 220", "XL"): 1,
    ("دارما", "D 220", "XXL"): 2,
    ("دارما", "D 550", "XL"): 1,
    ("دارما", "op", "L"): 1,
    ("دارما", "op", "XL"): 1,
    ("دارما", "pack 5", "M"): 3,
    ("دارما", "pack 5", "L"): 3,
    ("دارما", "pack 5", "XL"): 2,
    ("دارما", "pack 5", "XXL"): 5,
    ("دارما", "pack 5", "3XL"): 6,
    ("دارما", "rah-110", "M"): 1,
    ("دارما", "rah-110", "L"): 2,
    ("دارما", "rah-110", "XL"): 2,
    ("دارما", "rah-110", "XXL"): 1,
    ("دارما", "rah-220", "L"): 1,
    ("دارما", "rah-220", "XXL"): 1,
}
SAMPLE_TOTAL_PACKS = 44
SAMPLE_GROUPED_LINES = 23
