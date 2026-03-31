window.addEventListener('load', function() {
    const $ = (typeof django !== 'undefined' && django.jQuery) ? django.jQuery : (typeof jQuery !== 'undefined' ? jQuery : null);
    
    if (!$) {
        console.error("admin_chained_dropdown.js could not initialize: jQuery is missing.");
        return;
    }

    $(document).ready(function() {
        const $categoryField = $('#id_category');
        const $industryField = $('#id_industry');
        const endpointUrl = '/admin/accounts/user/industry-by-category/';

        function loadIndustries(categoryId, selectedIndustryId) {
            // Disable while loading
            $industryField.prop('disabled', true);
            
            if (!categoryId) {
                $industryField.empty();
                $industryField.append($('<option></option>').attr('value', '').text('---------'));
                return;
            }

            $.ajax({
                url: endpointUrl,
                data: {
                    'category_id': categoryId
                },
                dataType: 'json',
                success: function(data) {
                    $industryField.empty();
                    $industryField.append($('<option></option>').attr('value', '').text('---------'));
                    
                    $.each(data, function(index, item) {
                        const $option = $('<option></option>').attr('value', item.id).text(item.name);
                        $industryField.append($option);
                    });
                    
                    if (selectedIndustryId) {
                        $industryField.val(selectedIndustryId);
                        
                        // If selectedIndustryId is not in the list, set back to empty
                        if (!$industryField.val()) {
                            $industryField.val('');
                        }
                    }
                    
                    $industryField.prop('disabled', false);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    console.error('AJAX Error:', textStatus, errorThrown);
                    $industryField.prop('disabled', false); // Enable as a fallback
                }
            });
        }

        if ($categoryField.length && $industryField.length) {
            const initialCategoryId = $categoryField.val();
            const initialIndustryId = $industryField.val();
            
            if (initialCategoryId) {
                loadIndustries(initialCategoryId, initialIndustryId);
            } else {
                $industryField.prop('disabled', true);
            }

            $categoryField.on('change', function() {
                const categoryId = $(this).val();
                loadIndustries(categoryId, null);
            });
        } else {
            console.error("CRITICAL ERROR: Could not find #id_category or #id_industry on the page.");
        }
    });
});
