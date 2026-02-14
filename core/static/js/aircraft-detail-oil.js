function oilMixin() {
    return makeConsumableMixin({
        prefix:       'oil',
        endpoint:     'oil_records',
        responseKey:  'oil_records',
        chartCanvasId: 'oilChart',
        chartMetric:  (hoursDelta, qty) => (hoursDelta / qty).toFixed(1),
        chartLabel:   'Hours per Quart',
        chartColor:   '#0066cc',
        chartColorBg: 'rgba(0, 102, 204, 0.1)',
        addedMsg:     'Oil record added',
        updatedMsg:   'Oil record updated',
    });
}
