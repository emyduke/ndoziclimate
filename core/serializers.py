from rest_framework import serializers

NIGERIAN_STATES = [
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "FCT",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
]

PROPERTY_TYPES = [
    "Residential Land",
    "Commercial Land",
    "Industrial Land",
    "Residential Building",
    "Commercial Building",
    "Agricultural Land",
]

LEGACY_PROPERTY_TYPE_MAP = {
    "residential": "Residential Building",
    "commercial": "Commercial Building",
    "industrial": "Industrial Land",
    "agricultural": "Agricultural Land",
    "mixed": "Commercial Land",
}


class AssessmentInputSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=4.0, max_value=14.0)
    lng = serializers.FloatField(min_value=2.7, max_value=15.0)
    state = serializers.ChoiceField(choices=NIGERIAN_STATES)
    property_type = serializers.CharField(max_length=80)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_property_type(self, value: str) -> str:
        normalized = LEGACY_PROPERTY_TYPE_MAP.get(value, value)
        if normalized not in PROPERTY_TYPES:
            raise serializers.ValidationError("Unsupported property type.")
        return normalized
