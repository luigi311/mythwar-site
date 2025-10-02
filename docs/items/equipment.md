# Equipment

## Needs to be updated/validated against osmw


Below is an index of equipment families by slot and race/gender. Click a family to see its tier table.

## Weapons
{{ gear_index("Weapon", include_empty=True) }}

## Armors
{{ gear_index("Armor", include_empty=True) }}

## Helmets
{{ gear_index("Helmet", include_empty=True) }}

## Shoes
{{ gear_index("Shoes", include_empty=True) }}

## Bangles
{{ gear_index("Bangle", include_empty=True) }}

## Necklaces
{{ gear_index("Necklace", include_empty=True) }}

---

# Family Tables

{% for e in equipment %}
{{ gear_family_table_by_obj(e) }}

{% endfor %}
