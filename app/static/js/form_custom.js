document.addEventListener('DOMContentLoaded', function() {
    // PAR slider logic
    const parSlider = document.getElementById('par');
    const parValue = document.getElementById('par_value');
    const bargraph = document.getElementById('par-bargraph');

    if (parSlider && parValue && bargraph) {
        function updateParValue(val) {
            parValue.textContent = val;
        }

        function getGradient(val) {
            const min = parseInt(parSlider.min, 10);
            const max = parseInt(parSlider.max, 10);
            const percent = ((val - min) / (max - min));
            const percent100 = percent * 100;

            let stopColor;
            let stops;
            if (percent <= 0.533) {
                const t = percent / 0.533;
                stopColor = interpolateColor([34,51,85], [255,251,224], t);
                stops = `
                    #223355 0%,
                    ${stopColor} ${percent100}%,
                    #e0e0e0 ${percent100}%,
                    #e0e0e0 100%
                `;
            } else {
                const t = (percent - 0.533) / (1 - 0.533);
                stopColor = interpolateColor([255,251,224], [255,51,51], t);
                stops = `
                    #223355 0%,
                    #fffbe0 53.3%,
                    ${stopColor} ${percent100}%,
                    #e0e0e0 ${percent100}%,
                    #e0e0e0 100%
                `;
            }
            return `linear-gradient(to right,${stops})`;
        }

        function interpolateColor(start, end, t) {
            const r = Math.round(start[0] + (end[0] - start[0]) * t);
            const g = Math.round(start[1] + (end[1] - start[1]) * t);
            const b = Math.round(start[2] + (end[2] - start[2]) * t);
            return `rgb(${r},${g},${b})`;
        }

        function update() {
            const val = parseInt(parSlider.value, 10);
            updateParValue(val);
            bargraph.style.background = getGradient(val);
            bargraph.style.height = '40px';
        }

        window.addEventListener('resize', update);
        parSlider.addEventListener('input', update);
        parSlider.addEventListener('change', update);

        setTimeout(update, 0);
    }

    // Test radio logic
    fetch('/api/tests/get/latest')
        .then(response => response.json())
        .then(data => {
            const label = document.getElementById('test_id_current_label');
            const radio = document.getElementById('test_id_current');
            if (label && radio) {
                if (data && data.result) {
                    const test = data.result;
                    let text = test.test_date && test.test_time
                        ? `${test.test_date} ${test.test_time}`
                        : 'Test #' + test.id;
                    label.textContent = text;
                    radio.value = test.id;
                } else {
                    label.textContent = 'No tests found';
                    radio.value = '';
                }
            }
        })
        .catch(() => {
            const label = document.getElementById('test_id_current_label');
            const radio = document.getElementById('test_id_current');
            if (label && radio) {
                label.textContent = 'No tests found';
                radio.value = '';
            }
        });

    // Taxonomy species dropdown logic (filter by coral_type, not species)
    const typeSelect = document.getElementById('coral_type');
    const speciesSelect = document.getElementById('coral_species');

    typeSelect.addEventListener('change', function() {
        const selectedType = this.value;
        if (!selectedType) {
            speciesSelect.innerHTML = '<option value="">Select type first...</option>';
            speciesSelect.disabled = true;
            return;
        }
        speciesSelect.innerHTML = '<option value="">Loading...</option>';
        speciesSelect.disabled = true;
        fetch(`/api/taxonomy/by_type?type=${encodeURIComponent(selectedType)}`)
            .then(res => res.json())
            .then(data => {
                if (!data.length) {
                    speciesSelect.innerHTML = '<option value="">No species found for this type</option>';
                    speciesSelect.disabled = true;
                    return;
                }
                speciesSelect.innerHTML = '<option value="">Select species...</option>' +
                    data.map(t => `<option value="${t.id}">${t.common_name} (${t.species})</option>`).join('');
                speciesSelect.disabled = false;
            });
    });

    // Populate origin dropdown from DB
    const originSelect = document.getElementById('origin');
    if (originSelect) {
        fetch('/api/taxonomy/origins/all')
            .then(res => res.json())
            .then(data => {
                if (!data.length) {
                    originSelect.innerHTML = '<option value="">No origins found</option>';
                    return;
                }
                originSelect.innerHTML = '<option value="">Select origin...</option>' +
                    data.map(o => `<option value="${o}">${o}</option>`).join('');
            });
    }
});