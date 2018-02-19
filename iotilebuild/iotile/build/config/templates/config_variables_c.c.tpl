#define NOEXTERNAPPINFO
#include "config_variables_c.h"
#undef NOEXTERNAPPINFO

#include "cdb_application.h"

/* Required Config Variables */
{% for variable in configs.values() | selectattr("required") %}
{{ "config_%s_t" % variable.name if variable.array else variable.type }}  __attribute__((section(".required_config"))) {{ variable.name }};
{% endfor %}

/* Optional Config Variables */
{% for variable in configs.values() | rejectattr("required") %}
{% if variable.array %}
    {% if variable.default_value is string %}
config_{{ variable.name }}_t __attribute__((section(".optional_config"))) {{variable.name}} = {{'{'}}{{variable.default_size}}, 0, "{{ variable.default_value }}"{{'}'}};
    {% else %}
config_{{ variable.name }}_t __attribute__((section(".optional_config"))) {{variable.name}} = {{'{'}}{{variable.default_size}}, 0, {{"{"}}{{ variable.default_value | join(', ') }}{{"}"}}{{'}'}};
    {% endif %}
{% else %}
{{ variable.type }} __attribute__((section(".optional_config"))) {{ variable.name }} = {{ variable.default_value }};
{% endif %}
{% endfor %}

{% if configs | length > 0 %}
/* Config Variable Map */
const cdb_config_entry cdb_config_map[kNumTotalConfigs] = 
{
{% if configs.values() | selectattr('required') | list | count > 0 %}
    /* Required Config Variables */
{% for id, config in configs | dictsort if config.required %}
    {&{{config.name}}, {{"0x%04X" % id}}, {{config.total_size}}, {{ config.array | int }}{{'}'}}{%+ if loop.index != configs | length %},
{% endif %}
{% endfor %}

{% endif %}
    /* Optional Config Variables */
{% for id, config in configs | dictsort if not config.required %}
    {&{{config.name}}, {{"0x%04X" % id}}, {{config.total_size}}, {{ config.array | int }}{{'}'}}{%+ if loop.index != (configs.values() | rejectattr("required") | list | length) %},
{% endif %}
{% endfor %}
};
{% endif %}