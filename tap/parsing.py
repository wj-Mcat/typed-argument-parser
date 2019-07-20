from argparse import ArgumentParser
from copy import deepcopy
import json
from pprint import pformat
import sys
import time
from typing import Any, Dict, Optional, Sequence

from tap.parse_docstrings import extract_descriptions
from tap.utils import get_git_root, get_git_url, has_git, has_uncommitted_changes


class Tap(ArgumentParser):

    def __init__(self,
                 *args,
                 verbose: bool = False,
                 **kwargs):
        self.verbose = verbose

        # Get descriptions from the doc string
        self.description, self.variable_description = extract_descriptions(self.__doc__)

        super(Tap, self).__init__(description=self.description, *args, **kwargs)

        self.add_arguments()
        self._add_remaining_arguments()

    def add_argument(self, *args, **kwargs) -> None:
        # Get variable name
        variable = self._get_optional_kwargs(*args, **kwargs)['dest']

        # Get type and help if not specified
        if variable in self.__annotations__:
            annotation = self.__annotations__[variable]
            kwargs['type'] = kwargs.get('type', annotation)
            kwargs['help'] = kwargs.get('help', f'({annotation.__name__}) {self.variable_description[variable]}')

        # Get default if not specified
        if hasattr(self, variable):
            kwargs['default'] = kwargs.get('default', getattr(self, variable))

        super(Tap, self).add_argument(*args, **kwargs)

    def _add_remaining_arguments(self) -> None:
        current_arguments = {action.dest for action in self._actions}

        for variable in self.__annotations__.keys():
            if variable not in current_arguments:
                required = not hasattr(self, variable)
                self.add_argument(f'--{variable}', required=required)

    def add_arguments(self) -> None:
        """Explicitly add arguments to the parser if not using default settings."""
        pass

    def _parse_args(self,
                    args: Optional[Sequence[str]] = None,
                    namespace: Optional['Tap'] = None) -> None:
        default_namespace = super(Tap, self).parse_args(args, namespace)

        for variable, value in vars(default_namespace).items():
            # Check if variable has been defined
            if variable not in self.__annotations__:
                raise ValueError(f'Variable "{variable}" is not defined in class "{self.__class__.__name__}.')

            # Ensure the variable is of the right type
            variable_type, arg_type = self.__annotations__[variable], type(value)
            if variable_type != arg_type:
                raise ValueError(f'Variable "{variable}" of type "{arg_type}" does not match annotation type '
                                 f'"{variable_type}" for class "{self.__class__.__name__}".')

            # Set variable (and deepcopy)
            setattr(self, variable, deepcopy(value))

    def validate_args(self) -> None:
        """Perform argument validation to ensure valid argument combinations."""
        pass

    def process_args(self) -> None:
        """Perform additional argument processing."""
        pass

    @staticmethod
    def get_reproducibility_info() -> Dict[str, str]:
        """Gets a dictionary of reproducibility information."""
        reproducibility = {
            'command_line': f'python {" ".join(sys.argv)}',
            'time': time.strftime('%c')
        }

        if has_git():
            reproducibility['git_root'] = get_git_root()
            reproducibility['git_url'] = get_git_url()
            reproducibility['git_has_uncommitted_changes'] = has_uncommitted_changes()

        return reproducibility

    def get_arg_log(self) -> Dict[str, Any]:
        """Gets all args plus reproducibility info."""
        arg_log = self.as_dict()
        arg_log['reproducibility'] = self.get_reproducibility_info()

        return arg_log

    def parse_args(self,
                   args: Optional[Sequence[str]] = None,
                   namespace: Optional['Tap'] = None) -> 'Tap':
        self._parse_args(args, namespace)
        self.validate_args()
        self.process_args()

        return self

    def as_dict(self) -> Dict[str, Any]:
        """ Return only the member variables, which correspond to the  """
        # Required arguments assigned to the instance
        required_args = {
            var: getattr(self, var)
            for var, val in self.__class__.__dict__.items()
            if not var.startswith('_') and not callable(val)
            }

        # Arguments that are not required must have types and not be set
        not_required_args = {
            var: getattr(self, var)
            for var, val in self.__annotations__.items()
            }

        return {**required_args, **not_required_args}

    def save(self, path: str) -> None:
        """
        Saves the arguments in JSON format.

        :param path: Path to a JSON file.
        """
        with open(path, 'w') as f:
            json.dump(self.get_arg_log(), f, indent=4, sort_keys=True)

    def __str__(self) -> str:
        """Pretty prints the arg log."""
        return pformat(self.as_dict())
