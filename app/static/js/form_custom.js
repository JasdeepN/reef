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

    // Populate tank dropdown
    fetch('/api/get/raw/tanks')
        .then(response => response.json())
        .then(data => {
            const tankSelect = document.getElementById('tank_id');
            if (!tankSelect) return;
            // Use the correct array from the API response
            const tanks = data.data || [];
            tankSelect.options.length = 1;
            if (Array.isArray(tanks) && tanks.length > 0) {
                tanks.forEach(tank => {
                    const opt = document.createElement('option');
                    opt.value = tank.id;
                    opt.textContent = tank.name;
                    tankSelect.appendChild(opt);
                });
                if (tanks.length === 1) {
                    tankSelect.value = tanks[0].id;
                    // tankSelect.disabled = true;
                }
            }
        });

    // Auto-select tank if only one option
    const tankSelect = document.getElementById('tank_id');
    if (tankSelect && tankSelect.dataset.singleTank) {
        tankSelect.value = tankSelect.dataset.singleTank;
        // Do NOT disable the select, so it gets submitted!
    }

    // Populate test results dropdown as before
    fetch('/api/tests/get/latest')
        .then(response => response.json())
        .then(data => {
            const currentLabel = document.getElementById('test_id_current_label');
            if (data && data.result) {
                const test = data.result;
                let label = test.test_date && test.test_time
                    ? `${test.test_date} ${test.test_time}`
                    : 'Test #' + test.id;
                currentLabel.textContent = label;
                document.getElementById('test_id_current').value = test.id;
            } else {
                currentLabel.textContent = 'No tests found';
            }
        })
        .catch(() => {
            const currentLabel = document.getElementById('test_id_current_label');
            currentLabel.textContent = 'No tests found';
        });

    // Cache all genus data for filtering
    let allGenus = [];

    // Fetch all genus with type info
    fetch('/api/taxonomy/genus/all')
        .then(response => response.json())
        .then(data => {
            allGenus = Array.isArray(data) ? data : [];
            // Do NOT call populateGenus() here!
            // Only call it after a type is selected
        });

    // Populate vendors dropdown without removing the "None" option
    fetch('/api/get/raw/vendors')
        .then(response => response.json())
        .then(data => {
            const vendorsSelect = document.getElementById('vendors_id');
            if (!vendorsSelect) return;
            // Preserve the "None" option
            const noneOption = vendorsSelect.querySelector('option[value=""]');
            vendorsSelect.innerHTML = '';
            if (noneOption) {
                vendorsSelect.appendChild(noneOption);
            } else {
                // Fallback in case "None" is missing
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'None';
                vendorsSelect.appendChild(opt);
            }
            // Use the correct array from the API response
            const vendors = data.data || [];
            if (Array.isArray(vendors) && vendors.length > 0) {
                vendors.forEach(vendor => {
                    const opt = document.createElement('option');
                    opt.value = vendor.id;
                    opt.textContent = vendor.name;
                    vendorsSelect.appendChild(opt);
                });
            }
        });

    // Populate genus dropdown based on selected type
    function populateGenus() {
        const genusSelect = document.getElementById('genus_id');
        const typeSelect = document.getElementById('type');
        if (!genusSelect || !typeSelect) return;
        const selectedType = typeSelect.value;
        genusSelect.innerHTML = '<option value="">Select genus...</option>';
        let filtered = allGenus;
        if (selectedType) {
            filtered = allGenus.filter(g => g.type === selectedType);
        }
        filtered.forEach(genus => {
            const opt = document.createElement('option');
            opt.value = genus.genus;
            opt.textContent = genus.genus;
            genusSelect.appendChild(opt);
        });
        genusSelect.disabled = filtered.length === 0;
        // Reset species dropdown
        const speciesSelect = document.getElementById('species_id');
        if (speciesSelect) {
            speciesSelect.innerHTML = '<option value="">Select genus first...</option>';
            speciesSelect.disabled = true;
        }
    }

    // Re-filter genus when type changes
    const typeSelect = document.getElementById('type');
    const genusSelect = document.getElementById('genus_id');

    // Disable genus until a type is selected
    if (genusSelect) {
        genusSelect.disabled = true;
        genusSelect.innerHTML = '<option value="">Select type first...</option>';
    }
    console.log(`genusSelect: ${genusSelect.val}, typeSelect: ${typeSelect.val}`);
    
    // When type changes, enable and populate genus
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            const selectedType = typeSelect.value;
            if (!selectedType) {
                genusSelect.disabled = true;
                genusSelect.innerHTML = '<option value="">Select type first...</option>';
            } else {
                populateGenus();
                genusSelect.disabled = false;
            }
        });
    }

    // Populate genus dropdown
    const speciesSelect = document.getElementById('species_id');
    const colorMorphsSelect = document.getElementById('color_morphs_id');

    // Store all species and color morphs for the selected genus
    let allSpecies = [];
    let allColorMorphs = [];

    // Disable color morphs by default
    if (colorMorphsSelect) {
        colorMorphsSelect.disabled = true;
        colorMorphsSelect.innerHTML = '<option value="">Select genus first...</option>';
    }

    if (genusSelect && speciesSelect && colorMorphsSelect) {
        genusSelect.addEventListener('change', function() {
            const genus = this.value;
            speciesSelect.innerHTML = '<option value="">Loading...</option>';
            speciesSelect.disabled = true;
            colorMorphsSelect.innerHTML = '<option value="">Loading...</option>';
            colorMorphsSelect.disabled = true;

            if (!genus) {
                speciesSelect.innerHTML = '<option value="">Select genus first...</option>';
                speciesSelect.disabled = true;
                colorMorphsSelect.innerHTML = '<option value="">Select genus first...</option>';
                colorMorphsSelect.disabled = true;
                allSpecies = [];
                allColorMorphs = [];
                return;
            }

            // Combined request for both species and color morphs
            fetch(`/api/taxonomy/genus/details?genus=${encodeURIComponent(genus)}`)
                .then(response => response.json())
                .then(data => {
                    // Save all species and color morphs for later filtering
                    allSpecies = Array.isArray(data.species) ? data.species : [];
                    allColorMorphs = Array.isArray(data.color_morphs) ? data.color_morphs : [];

                    // Populate species
                    speciesSelect.innerHTML = '<option value="">Select species...</option>';
                    allSpecies.forEach(species => {
                        const opt = document.createElement('option');
                        opt.value = species.id; // taxonomy.id
                        opt.textContent = species.species ? species.species : 'N/A';
                        speciesSelect.appendChild(opt);
                    });
                    speciesSelect.disabled = allSpecies.length === 0;

                    // Populate color morphs
                    colorMorphsSelect.innerHTML = '<option value="">Select color morph...</option>';
                    allColorMorphs.forEach(morph => {
                        const opt = document.createElement('option');
                        opt.value = morph.id;
                        opt.textContent = morph.name;
                        colorMorphsSelect.appendChild(opt);
                    });
                    colorMorphsSelect.disabled = allColorMorphs.length === 0;
                });
        });

        // When species is selected, filter color morphs to only those for that species
        speciesSelect.addEventListener('change', function() {
            const selectedSpeciesId = this.value;
            if (!selectedSpeciesId) {
                // Show all morphs for the genus if no species selected
                colorMorphsSelect.innerHTML = '<option value="">Select color morph...</option>';
                allColorMorphs.forEach(morph => {
                    const opt = document.createElement('option');
                    opt.value = morph.id;
                    opt.textContent = morph.name;
                    colorMorphsSelect.appendChild(opt);
                });
                colorMorphsSelect.disabled = allColorMorphs.length === 0;
                return;
            }
            // Filter morphs by selected species
            colorMorphsSelect.innerHTML = '<option value="">Select color morph...</option>';
            const filteredMorphs = allColorMorphs.filter(morph => String(morph.taxonomy_id) === String(selectedSpeciesId));
            filteredMorphs.forEach(morph => {
                const opt = document.createElement('option');
                opt.value = morph.id;
                opt.textContent = morph.name;
                colorMorphsSelect.appendChild(opt);
            });
            colorMorphsSelect.disabled = filteredMorphs.length === 0;
        });

        // When color morph is selected, set the species dropdown to the correct species
        colorMorphsSelect.addEventListener('change', function() {
            const selectedMorphId = this.value;
            if (!selectedMorphId) return;
            const morph = allColorMorphs.find(m => String(m.id) === String(selectedMorphId));
            if (morph && morph.taxonomy_id) {
                // Only set the species, do not trigger change or repopulate morphs
                speciesSelect.value = String(morph.taxonomy_id);
            }
        });
    }

    // Helper to highlight a select for a moment
    function highlightSelect(selector) {
        const el = document.querySelector(selector);
        if (el) {
            el.classList.add('select-highlight');
            setTimeout(() => el.classList.remove('select-highlight'), 1500);
            el.focus();
        }
    }

    // Always highlight #type if genus, species, or color morph is clicked and type is not selected
    ['#genus_id', '#species_id', '#color_morphs_id'].forEach(sel => {
        const select = document.querySelector(sel);
        if (!select) return;
        // Always highlight #type if not selected
        function maybeHighlightType(e) {
            const typeSelect = document.querySelector('#type');
            if (!typeSelect || !typeSelect.value) {
                e.preventDefault();
                highlightSelect('#type');
            }
        }
        // On select itself (when enabled)
        select.addEventListener('click', maybeHighlightType);
        // On wrapper (for disabled or enabled)
        const wrapper = select.closest('.select-wrapper');
        if (wrapper) {
            wrapper.addEventListener('click', maybeHighlightType);
        }
    });

    // Existing logic for wrappers of disabled selects
    [
        { wrapper: '.select-wrapper', select: '#color_morphs_id', required: '#genus_id' },
        { wrapper: '.select-wrapper', select: '#species_id', required: '#genus_id' }
    ].forEach(pair => {
        const select = document.querySelector(pair.select);
        const wrapper = select ? select.closest(pair.wrapper) : null;
        if (select && wrapper) {
            wrapper.addEventListener('click', function (e) {
                if (select.disabled) {
                    e.preventDefault();
                    highlightSelect(pair.required);
                }
            });
        }
    });

    // Coral type defaults logic
    const coralDefaults = {
        'SPS': {
            lighting: 'High',
            par: 300,
            flow: 'High',
            feeding: 'Minimal',
            placement: 'Top'
        },
        'LPS': {
            lighting: 'Medium',
            par: 150,
            flow: 'Medium',
            feeding: 'Occasional',
            placement: 'Middle'
        },
        'Soft': {
            lighting: 'Low',
            par: 80,
            flow: 'Low',
            feeding: 'Optional',
            placement: 'Bottom'
        },
        'Zoanthid': {
            lighting: 'Low',
            par: 80,
            flow: 'Low',
            feeding: 'Optional',
            placement: 'Bottom'
        },
        'Mushroom': {
            lighting: 'Low',
            par: 60,
            flow: 'Low',
            feeding: 'Optional',
            placement: 'Bottom'
        },
        'Other': {
            lighting: '',
            par: '',
            flow: '',
            feeding: '',
            placement: ''
        }
    };

    const coralType = document.getElementById('coral_type');
    if (coralType) {
        coralType.addEventListener('change', function() {
            const type = this.value;
            const defaults = coralDefaults[type];
            if (defaults) {
                if (defaults.lighting !== undefined && document.getElementById('lighting'))
                    document.getElementById('lighting').value = defaults.lighting;
                if (defaults.par !== undefined && document.getElementById('par')) {
                    document.getElementById('par').value = defaults.par;
                    document.getElementById('par_value').textContent = defaults.par;
                    document.getElementById('par').dispatchEvent(new Event('input'));
                }
                if (defaults.flow !== undefined && document.getElementById('flow'))
                    document.getElementById('flow').value = defaults.flow;
                if (defaults.feeding !== undefined && document.getElementById('feeding'))
                    document.getElementById('feeding').value = defaults.feeding;
                if (defaults.placement !== undefined && document.getElementById('placement'))
                    document.getElementById('placement').value = defaults.placement;
            }
        });
    }

    // Enable Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.forEach(function (popoverTriggerEl) {
        new bootstrap.Popover(popoverTriggerEl);
    });

});