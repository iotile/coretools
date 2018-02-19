#ifndef __config_variables_c_h__
#define __config_variables_c_h__

#include <stdint.h>
#include <stdbool.h>
#include "cdb_application.h"

#define kNumRequiredConfigs {{ configs.values() | selectattr("required") | list | length }}
#define kNumTotalConfigs    {{ configs | length }}

{% for variable in configs.values() | selectattr("array") %}
typedef struct
{
    uint16_t length;
    uint16_t reserved;
    {{ variable.type }} data[{{ variable.count }}];
} config_{{ variable.name }}_t;

{% endfor %}

#ifndef NOEXTERNAPPINFO
{% for variable in configs.values() %}
{% if variable.array %}
extern config_{{ variable.name }}_t {{ variable.name }};
{% else %}
extern {{ variable.type }} {{ variable.name }};
{%endif %}
{% endfor %}

{% if configs | length > 0 %}
extern const cdb_config_entry cdb_config_map[kNumTotalConfigs];
{% endif %}
#endif /* NOEXTERNAPPINFO */

#endif /*__config_variables_c_h__ */
