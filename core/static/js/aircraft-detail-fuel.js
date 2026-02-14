function fuelMixin() {
    return makeConsumableMixin({
        prefix:       'fuel',
        endpoint:     'fuel_records',
        responseKey:  'fuel_records',
        chartCanvasId: 'fuelChart',
        chartMetric:  (hoursDelta, qty) => (qty / hoursDelta).toFixed(1),
        chartLabel:   'Gallons per Hour',
        chartColor:   '#009596',
        chartColorBg: 'rgba(0, 149, 150, 0.1)',
        addedMsg:     'Fuel record added',
        updatedMsg:   'Fuel record updated',
    });
}
