"""Fiche de test — Annexe d'audit, fully deterministic (conception §20.3)."""

import pytest


@pytest.mark.skip(reason="pending reporting.audit_annex implementation")
def test_versions_labeled_and_framework_versions_rendered():
    # given w3_versions[0] superseded, w3_versions[1] approved,
    # compliance_frameworks_versions={'RGPD': '2016/679', 'NIST': 'CSF 2.0'}
    # assert audit_doc row for w3_versions[0] labeled 'superseded'
    # assert audit_doc row for w3_versions[1] labeled 'approved'
    # assert audit_doc.rgpd_version_field == '2016/679'
    # assert audit_doc.nist_version_field == 'CSF 2.0'
    # assert every abnormal_event has a blank "Appréciation de l'auditeur" field
    pass
