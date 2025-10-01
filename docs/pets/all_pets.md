# All Pets

# Needs to be updated/validated against osmw


<div class="pet-wrap" markdown>

| Name | Species | GR | Skills | Stats | Source | Physical | Magical | Elemental |
| ---- | ------  | -- | ------ | ----- | ------ | -------- | ------- | --------- |
{%- for pet in pets %}
{{ macros.pet_row(pet) }}
{%- endfor %}

</div>