from health import views

ROUTER_REGISTRATIONS = [
    ('component-types', views.ComponentTypeViewSet),
    ('components', views.ComponentViewSet),
    ('document-collections', views.DocumentCollectionViewSet),
    ('documents', views.DocumentViewSet),
    ('document-images', views.DocumentImageViewSet),
    ('logbook-entries', views.LogbookEntryViewSet),
    ('squawks', views.SquawkViewSet),
    ('inspection-types', views.InspectionTypeViewSet),
    ('ads', views.ADViewSet),
    ('major-records', views.MajorRepairAlterationViewSet),
    ('inspections', views.InspectionRecordViewSet),
    ('ad-compliances', views.ADComplianceViewSet),
    ('consumable-records', views.ConsumableRecordViewSet),
    ('oil-analysis-reports', views.OilAnalysisReportViewSet),
    ('flight-logs', views.FlightLogViewSet),
]
