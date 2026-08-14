QUESTIONNAIRE_DEFINITIONS = {
    "general-health": {
        "id": "general-health@1.0",
        "version": "1.0",
        "prefill_fields": [
            "full_name", "identity_type", "masked_identity", "date_of_birth", "email",
            "country_code", "phone", "address", "postal_code", "ethnicity", "sex",
        ],
        "response_fields": [
            "current_medication", "medication_details", "drug_allergies", "allergy_details",
            "personal_history", "family_history", "smoking", "alcohol", "exercise",
        ],
        "required_consents": ["data_use", "declaration"],
    },
    "occupational-health": {
        "id": "occupational-health@1.0",
        "version": "1.0",
        "prefill_fields": [
            "full_name", "identity_type", "masked_identity", "date_of_birth", "email",
            "country_code", "phone", "address", "postal_code", "ethnicity", "sex",
        ],
        "response_fields": [
            "current_medication", "medication_details", "drug_allergies", "allergy_details",
            "personal_history", "family_history", "smoking", "alcohol", "exercise", "screening_type",
        ],
        "required_consents": ["data_use", "employer_insurer_disclosure", "declaration"],
    },
}
